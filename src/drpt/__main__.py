import click

from drpt import __version__
from drpt.drpt import DataReleasePrep

@click.command(no_args_is_help=True)
@click.option("--dry-run", "-d", is_flag=True, help="Dry run")
@click.option("--verbose", "-v", is_flag=True, help="Verbose")
@click.option("--nrows", "-n", default=None, help="Number of rows to read")
@click.option("--no-scaling", "-ns", is_flag=True, help="Disable default Min/Max scaling")
@click.option("--limits-file", "-l", type=click.Path(exists=True), help="Limits file")
@click.option("--output-file", "-o", type=click.Path(), help="Output file")
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
    no_scaling):
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
            no_scaling
        )
        release.release_prep()
        release.generate_report()
    except Exception as e:
        print(e)

if __name__ == "__main__":
    main()
