import traceback

import click

from drpt import __version__
from drpt.drpt import DataReleasePrep


@click.command(no_args_is_help=True)
@click.option(
    "--dry-run",
    "-d",
    is_flag=True,
    help="Generate only the report without the release dataset",
)
@click.option("--verbose", "-v", is_flag=True, help="Verbose [Not implemented]")
@click.option(
    "--nrows",
    "-n",
    default=None,
    help="Number of rows to read from a CSV file. Doesn't work with parquet files.",
)
@click.option("--limits-file", "-l", type=click.Path(exists=True), help="Limits file")
@click.option("--output-file", "-o", type=click.Path(), help="Output file")
@click.option(
    "--debug", is_flag=True, help="Enable debug mode showing full trace", hidden=True
)
@click.argument("recipe-file", type=click.Path(exists=True))
@click.argument("input-file", type=click.Path(exists=True))
@click.version_option(version=__version__)
def main(
    recipe_file,
    input_file,
    output_file,
    limits_file,
    dry_run,
    verbose,
    nrows,
    debug,
):
    """Data Release Preparation Tool (drpt)

    Tool for preparing a dataset for publishing by dropping, renaming, scaling, and obfuscating columns defined in a recipe."""
    try:
        release = DataReleasePrep(
            recipe_file,
            input_file,
            output_file,
            limits_file,
            dry_run,
            verbose,
            nrows,
            __version__,
        )
        release.release_prep()
        release.generate_report()
    except Exception as e:
        print(e)
        if debug:
            print(traceback.print_exc())


if __name__ == "__main__":
    main()
