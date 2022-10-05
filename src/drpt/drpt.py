#!/usr/bin/env python3.9
import json
import logging
import re
from pathlib import Path

import jsonschema
import pandas as pd

RECIPE_SCHEMA = {
    "type": "object",
    "properties": {
        "version": {"type": "string"},
        "actions": {
            "type": "object",
            "properties": {
                "drop": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "drop-constant-columns": {"type": "boolean"},
                "obfuscate": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "disable-scaling": {"type": "boolean"},
                "skip-scaling": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "rename": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "patternProperties": {"^.*$": {"type": "string"}},
                    },
                },
            },
        },
    },
    "required": ["version", "actions"],
}


class DataReleasePrep:
    def __init__(
        self,
        recipe_file,
        input_file,
        output_file,
        limits_file,
        dry_run,
        verbose,
        nrows,
        tool_version,
    ):
        self.recipe_file = recipe_file
        self.input_file = input_file
        self.output_file = output_file
        self.limits_file = limits_file
        self.dry_run = dry_run
        self.verbose = verbose
        self.nrows = nrows
        self.limits = None
        self.report = []
        self.logger = None

        self.input_file_stem = Path(self.input_file).stem
        self.input_file_suffix = Path(self.input_file).suffix

        self._init_logger()
        self._check_cmd_args()
        self._read_check_recipe()
        self.data = self._read_data()

        if self.limits_file is not None:
            self._read_limits()

        self._report_log("drpt_version", "", tool_version)

    def _init_logger(self):
        self.logger = logging.getLogger("drpt")
        self.logger.setLevel(logging.INFO)
        ch = logging.StreamHandler()
        cf = logging.Formatter("%(message)s")
        ch.setFormatter(cf)
        self.logger.addHandler(ch)

    def _report_log(self, action, column, details):
        self.report.append((action, column, details))

    def _check_cmd_args(self):
        if self.recipe_file is None and self.generate_recipe is False:
            raise ValueError("No recipe provided")

    def _read_check_recipe(self):
        self.recipe = json.load(open(self.recipe_file))
        jsonschema.validate(self.recipe, RECIPE_SCHEMA)

        # Define the output file if not given
        if self.output_file is None:
            self.output_file = (
                self.input_file_stem
                + "_release_"
                + self.recipe["version"]
                + self.input_file_suffix
            )
        self._report_log("recipe_version", "", self.recipe["version"])

    def _read_limits(self):
        self.logger.info("Reading limits...")
        if Path(self.limits_file).suffix == ".csv":
            limits_df = pd.read_csv(
                self.limits_file, header=None, skip_blank_lines=True
            )
            # Remove header row if present
            if limits_df.iloc[0, :].tolist() == ["column", "min", "max"]:
                limits_df.drop(0, inplace=True)

            limits_df.columns = ["column", "min", "max"]
            limits_df.set_index("column", inplace=True)
            self.limits = limits_df.to_dict(orient="index")

        # TODO: Implement JSON input
        # if Path(self.limits_file).suffix == ".json":
        #     self.limits = pd.read_json(self.limits_file, orient="records")

    def _read_data(self):
        if self.input_file.endswith(".csv"):
            self.logger.info("Reading CSV data...")
            data = pd.read_csv(self.input_file, nrows=self.nrows)
        elif self.input_file.endswith(".parquet"):
            self.logger.info("Reading Parquet data...")
            # FIXME: Add message to say that nrows is not supported for parquet
            data = pd.read_parquet(self.input_file, engine="pyarrow")
        return data

    def _drop_columns(self):
        if "drop" in self.recipe["actions"]:
            self.logger.info("Dropping columns...")
            for pat in self.recipe["actions"]["drop"]:
                for col in self.data.columns:
                    if re.fullmatch(pat, col):
                        self._report_log("DROP", col, "")
                        self.data.drop(col, axis=1, inplace=True)

    def _drop_constant_columns(self):
        if self.recipe["actions"].get("drop-constant-columns", False):
            self.logger.info("Dropping constant columns...")
            for col in self.data.columns:
                if self.data[col].nunique() == 1:
                    self._report_log("DROP_CONSTANT", col, "")
                    self.data.drop(col, axis=1, inplace=True)

    def _obfuscate_columns(self):
        if "obfuscate" in self.recipe["actions"]:
            self.logger.info("Obfuscating columns...")
            for pat in self.recipe["actions"]["obfuscate"]:
                for col in self.data.columns:
                    if re.fullmatch(pat, col):
                        self._report_log("OBFUSCATE", col, "")
                        if not self.dry_run:
                            self.data[col] = self.data[col].astype("category").cat.codes

    def _scale_columns(self):
        self.logger.info("Scaling columns...")
        for col in self.data.select_dtypes(include="number").columns.tolist():
            if col in self.recipe["actions"]["obfuscate"]:
                continue

            skip_scaling = False
            no_scaling = self.recipe["actions"].get("skip-scaling", [])
            for pat in no_scaling:
                if re.fullmatch(pat, col):
                    skip_scaling = True
                    break

            if not skip_scaling:
                if self.limits is not None and col in self.limits:
                    min, max = self.limits[col]["min"], self.limits[col]["max"]
                    if pd.isna(min):
                        min = self.data[col].min()
                    if pd.isna(max):
                        max = self.data[col].max()
                    self._report_log("SCALE_CUSTOM", col, f"[{min},{max}]")
                    if not self.dry_run:
                        self.data[col] = (self.data[col] - min) / (max - min)
                else:
                    self._report_log(
                        "SCALE_DEFAULT",
                        col,
                        f"[{self.data[col].min()},{self.data[col].max()}]",
                    )
                    if not self.dry_run:
                        self.data[col] = (self.data[col] - self.data[col].min()) / (
                            self.data[col].max() - self.data[col].min()
                        )

    def _rename_columns(self):
        if "rename" in self.recipe["actions"]:
            self.logger.info("Renaming columns...")
            for renaming in self.recipe["actions"]["rename"]:
                pat, repl = renaming.popitem()
                pat = re.compile(pat)

                # Apply regex substitution to all columns
                replacements = {
                    col: pat.sub(repl, col)
                    for col in self.data.columns
                    if pat.fullmatch(col)
                }

                # Calculate the number of replacements with the same target
                count = {repl: 0 for repl in replacements.values()}
                for repl in replacements.values():
                    count[repl] += 1
                orig_count = count.copy()

                # Append a number to the end of the target if there are multiple
                for col, repl in replacements.items():
                    if orig_count[repl] > 1:
                        replacements[
                            col
                        ] = f"{repl}_{orig_count[repl]-count[repl]+1}"  # TODO: Make the pattern configurable
                        count[repl] -= 1

                # Rename the columns
                for col, repl in replacements.items():
                    self._report_log("RENAME", col, repl)
                    if not self.dry_run:
                        self.data.rename(columns={col: repl}, inplace=True)

    def release_prep(self):
        self._drop_columns()
        self._drop_constant_columns()
        self._obfuscate_columns()
        if not self.recipe["actions"].get("disable-scaling", False):
            self._scale_columns()
        self._rename_columns()
        if not self.dry_run:
            if self.input_file_suffix == ".csv":
                self.data.to_csv(
                    self.output_file,
                    index=False,
                )
            elif self.input_file_suffix == ".parquet":
                self.data.to_parquet(
                    self.output_file,
                    engine="pyarrow",
                    index=False,
                )

    def generate_report(self):
        self.logger.info("Generating report...")
        report_df = pd.DataFrame(self.report, columns=["action", "column", "details"])
        report_df.to_csv(Path(self.output_file).stem + "_report.csv", index=True)
