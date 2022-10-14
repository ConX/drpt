#!/usr/bin/env python3.9
import json
import re
from os import mkdir
from pathlib import Path

import jsonschema
import numpy as np
import pandas as pd
from dask import compute, delayed

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
            "additionalProperties": False,
        },
    },
    "required": ["version", "actions"],
    "additionalProperties": False,
}


@delayed
def min_max_scale(s):
    min = np.nanmin(s)
    max = np.nanmax(s)
    if max == min:
        exit(
            " ❌ Scaling failed: There is at least one constant column.\n   Consider dropping constant columns, disabling or skip scaling."
        )
    return (s - min) / (max - min)


@delayed
def min_max_scale_limits(s, min_limit, max_limit):
    return (s - min_limit) / (max_limit - min_limit)


class ProgressMessage:
    def __init__(self, message, parent=None):
        self.message = message
        self.children = []
        self.level = 0 if parent is None else parent.level + 1
        if parent is not None:
            if len(parent.children) == 0:
                print("", end="\n")
            parent.children.append(self)

    def __enter__(self):
        print("\033[?25l", end="")
        print("  " * self.level, end="")
        print(f" ⬜  {self.message}", end="\r")
        print("\b" * 10, end="")
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if len(self.children) > 0:
            self._clear_line(len(self.children) + 1)
        print("  " * self.level, end="")
        print(f" ✅  {self.message}", end="\r\n")
        for child in self.children:
            print("  " * (child.level), end="")
            print(f" ✅  {child.message}", end="\r\n")
        print("\033[?25h", end="")

    def _clear_line(self, n=1):
        for _ in range(n):
            print("\033[1A", end="\x1b[2K")


class DataReleasePrep:
    def __init__(
        self,
        recipe_file,
        input_file,
        limits_file,
        dry_run,
        verbose,
        nrows,
        output_directory,
        tool_version,
    ):
        self.recipe_file = recipe_file
        self.input_file = input_file
        self.limits_file = limits_file
        self.dry_run = dry_run
        self.verbose = verbose
        self.nrows = nrows
        self.limits = None
        self.report = []

        if output_directory is None:
            self.output_directory = str(Path(self.recipe_file).parent.absolute()) + "/"
        else:
            self.output_directory = str(Path(output_directory).absolute()) + "/"
            if not Path(self.output_directory).exists():
                mkdir(self.output_directory)

        self.input_file_stem = Path(self.input_file).stem
        self.input_file_suffix = Path(self.input_file).suffix

        self._check_cmd_args()
        self._read_check_recipe()
        self.data = self._read_data()

        if self.limits_file is not None:
            self._read_limits()

        self._report_log("drpt_version", "", tool_version)

    def _report_log(self, action, column, details):
        self.report.append((action, column, details))

    def _check_cmd_args(self):
        if self.recipe_file is None and self.generate_recipe is False:
            raise ValueError("No recipe provided")

    def _read_check_recipe(self):
        self.recipe = json.load(open(self.recipe_file))
        jsonschema.validate(self.recipe, RECIPE_SCHEMA)

        self.output_file = (
            self.output_directory
            + self.input_file_stem
            + "_release_"
            + self.recipe["version"]
            + self.input_file_suffix
        )
        self._report_log("recipe_version", "", self.recipe["version"])

    def _read_limits(self):
        with ProgressMessage("Reading limits..."):
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
            with ProgressMessage("Reading CSV data..."):
                data = pd.read_csv(self.input_file, nrows=self.nrows)
        elif self.input_file.endswith(".parquet"):
            # FIXME: Add message to say that nrows is not supported for parquet
            with ProgressMessage("Reading Parquet data..."):
                data = pd.read_parquet(self.input_file, engine="pyarrow")

        # Force unique index
        if not data.index.is_unique:
            data = data.reset_index(drop=True)
        return data

    def _drop_columns(self):
        if "drop" in self.recipe["actions"]:
            with ProgressMessage("Dropping columns..."):
                cols_to_drop = []
                for pat in self.recipe["actions"]["drop"]:
                    for col in self.data.columns:
                        if re.fullmatch(pat, col):
                            self._report_log("DROP", col, "")
                            cols_to_drop.append(col)
                self.data.drop(cols_to_drop, axis=1, inplace=True)

    def _drop_constant_columns(self):
        if self.recipe["actions"].get("drop-constant-columns", False):
            with ProgressMessage("Dropping constant columns..."):
                cols_to_drop = []
                for col in self.data.columns:
                    if self.data[col].nunique() == 1:
                        self._report_log("DROP_CONSTANT", col, "")
                        cols_to_drop.append(col)
                self.data.drop(cols_to_drop, axis=1, inplace=True)

    def _obfuscate_columns(self):
        if "obfuscate" in self.recipe["actions"]:
            with ProgressMessage("Obfuscating columns..."):
                for pat in self.recipe["actions"]["obfuscate"]:
                    for col in self.data.columns:
                        if re.fullmatch(pat, col):
                            col_cat = self.data[col].astype("category").cat
                            col_cat_map = {
                                cat: code for code, cat in enumerate(col_cat.categories)
                            }
                            self._report_log("OBFUSCATE", col, json.dumps(col_cat_map))
                            if not self.dry_run:
                                self.data[col] = col_cat.codes

    def _scale_columns(self):
        with ProgressMessage("Scaling columns...") as level1:
            min_max_scale_limit_cols = []
            min_max_scale_cols = []
            min_max_scale_limit_futures = []
            min_max_scale_futures = []
            with ProgressMessage("Preparing compute processes...", parent=level1):
                for col in self.data.select_dtypes(include="number").columns.tolist():
                    # Skip column if it has been obfuscated already
                    if col in self.recipe["actions"].get("obfuscate", []):
                        continue

                    # Skip column if it matches skip-scaling pattern
                    skip_scaling = False
                    no_scaling = self.recipe["actions"].get("skip-scaling", [])
                    for pat in no_scaling:
                        if re.fullmatch(pat, col):
                            skip_scaling = True
                            break

                    if not skip_scaling:
                        col_min = self.data[col].min()
                        col_max = self.data[col].max()
                        if self.limits is not None and col in self.limits:
                            min, max = self.limits[col]["min"], self.limits[col]["max"]
                            if min == max or (pd.isna(min) and pd.isna(max)):
                                self._report_log(
                                    "WARNING",
                                    col,
                                    f"Custom limits are the same: {min}. Reverting to min/max",
                                )
                                min, max = col_min, col_max
                                self._report_log("SCALE_DEFAULT", col, f"[{min},{max}]")
                            else:
                                if pd.isna(min):
                                    min = col_min
                                    self._report_log(
                                        "WARNING",
                                        col,
                                        "Custom min limit is NaN. Generating from data.",
                                    )
                                if pd.isna(max):
                                    max = col_max
                                    self._report_log(
                                        "WARNING",
                                        col,
                                        "Custom max limit is NaN. Generating from data.",
                                    )
                                self._report_log("SCALE_CUSTOM", col, f"[{min},{max}]")

                            assert max > min, (
                                "Max must be greater than min for column " + col
                            )

                            if not self.dry_run:
                                min_max_scale_limit_cols.append(col)
                                if self.data[col].dtype.name == "int64":
                                    min_max_scale_limit_futures.append(
                                        min_max_scale_limits(
                                            self.data[col].to_numpy(
                                                dtype=pd.Int64Dtype, na_value=np.nan
                                            ),
                                            min,
                                            max,
                                        )
                                    )
                                else:
                                    min_max_scale_limit_futures.append(
                                        min_max_scale_limits(
                                            self.data[col].to_numpy(na_value=np.nan),
                                            min,
                                            max,
                                        )
                                    )
                        else:
                            self._report_log(
                                "SCALE_DEFAULT",
                                col,
                                f"[{col_min},{col_max}]",
                            )
                            if not self.dry_run:
                                min_max_scale_cols.append(col)
                                if self.data[col].dtype.name == "int64":
                                    min_max_scale_futures.append(
                                        min_max_scale(
                                            self.data[col].to_numpy(
                                                dtype=pd.Int64Dtype, na_value=np.nan
                                            )
                                        )
                                    )
                                else:
                                    min_max_scale_futures.append(
                                        min_max_scale(
                                            self.data[col].to_numpy(na_value=np.nan)
                                        )
                                    )

            if not self.dry_run:
                if len(min_max_scale_limit_futures) > 0:
                    with ProgressMessage(
                        "Running limit scaling processes...",
                        parent=level1,
                    ):
                        computed_columns = compute(
                            *min_max_scale_limit_futures, scheduler="processes"
                        )
                        self.data.drop(min_max_scale_limit_cols, axis=1, inplace=True)
                        computed_columns = [
                            pd.Series(computed_column)
                            for computed_column in computed_columns
                        ]
                        computed_columns = pd.concat(computed_columns, axis=1)
                        computed_columns.columns = min_max_scale_limit_cols
                        self.data = self.data.merge(
                            computed_columns,
                            left_index=True,
                            right_index=True,
                        )

                if len(min_max_scale_futures) > 0:
                    with ProgressMessage(
                        "Running default min/max scaling processes...", parent=level1
                    ):
                        computed_columns = compute(
                            *min_max_scale_futures, scheduler="processes"
                        )
                        self.data.drop(min_max_scale_cols, axis=1, inplace=True)
                        computed_columns = [
                            pd.Series(computed_column)
                            for computed_column in computed_columns
                        ]
                        computed_columns = pd.concat(computed_columns, axis=1)
                        computed_columns.columns = min_max_scale_cols
                        self.data = self.data.merge(
                            computed_columns,
                            left_index=True,
                            right_index=True,
                        )

    def _rename_columns(self):
        if "rename" in self.recipe["actions"]:
            with ProgressMessage("Renaming columns..."):
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
                with ProgressMessage("Generating data release CSV file..."):
                    self.data.to_csv(
                        self.output_file,
                        index=False,
                    )
            elif self.input_file_suffix == ".parquet":
                with ProgressMessage("Generating data release Parquet file..."):
                    self.data.to_parquet(
                        self.output_file,
                        engine="pyarrow",
                        index=False,
                    )

    def generate_report(self):
        with ProgressMessage("Generating report..."):
            report_df = pd.DataFrame(
                self.report, columns=["action", "column", "details"]
            )
            report_df.to_csv(
                self.output_directory + Path(self.output_file).stem + "_report.csv",
                index=True,
            )
