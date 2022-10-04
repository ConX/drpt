# Data Release Preparation Tool

> :warning: This is currently at beta development stage and likely has a lot of bugs. Use the [issue tracker](https://github.com/ConX/drpt/issues) to report an bugs or feature requests.

## Description

Command-line tool for preparing a dataset for publishing by dropping, renaming, scaling, and obfuscating columns defined in a recipe.

After performing the operations defined in the recipe the tool generates the transformed dataset version and a CSV report listing the performed actions.

## Recipe 

The recipe is a JSON formatted file that includes what operations should be performed on the dataset. For versioning purposes, the recipe also contains a `version` key which is appended in the generated filenames and the report.

**Empty recipe:**
```json
{
  "version": "",
  "actions": {
    "drop": [],
    "rename": [],
    "obfuscate": [],
    "no-scaling": []
  }
}
```

The currently supported actions are:
  - `drop`: Column deletion
  - `rename`: Column renaming
  - `obfuscate`: Column obfuscation, where the listed columns are treated as categorical variables and then integer coded.
  - Column scaling, where by default all columns are Min/Max scaled, except those excluded (`no-scaling`). To disable scaling the `--no-scaling` command-line option can be used.

All column definitions above support regular expressions.

## Usage
```txt
Usage: drpt [OPTIONS] RECIPE_FILE INPUT_FILE

Options:
  -d, --dry-run           Generate only the report without the release dataset
  -v, --verbose           Verbose [Not implemented]
  -n, --nrows TEXT        Number of rows to read from a CSV file. Doesn't work with parquet files.
  -ns, --no-scaling       Disable default Min/Max scaling
  -l, --limits-file PATH  Limits file
  -o, --output-file PATH  Output file
  --version               Show the version and exit.
  --help                  Show this message and exit
```

### Example

**Input file:**
```csv
test1,test2,test3,test4,test5,test6,test7,test8,test9
1.1,1,one,2,0.234,0.3,-1,a,e
2.2,2,two,2,0.555,0.4,0,b,f
3.3,3,three,4,0.1,5,1,c,g
2.22,2,two,4,1,0,2.5,d,h
```

**Recipe:**
```json
{
  "version": "1.0",
  "actions": {
    "drop": ["test2", "test[8-9]"],
    "rename": [
      { "test1": "test1_renamed" },
      { "test([3-4])": "test\\1_regex_renamed" }
    ],
    "obfuscate": ["test3"],
    "no-scaling": ["test4"]
  }
}
```

**Result:**
```txt
test1_renamed,test3_regex_renamed,test4_regex_renamed,test5,test6,test7
0.0,0,2,0.1488888888888889,0.06,0.0
0.5000000000000001,2,2,0.5055555555555556,0.08,0.2857142857142857
1.0,1,4,0.0,1.0,0.5714285714285714
0.5090909090909091,2,4,1.0,0.0,1.0
```

**Report:**
```txt
,column,action,details
0,test2,dropped,
1,test8,dropped,
2,test9,dropped,
3,test3,obfuscated,
4,test1,scaled,0.0 - 1.0
5,test5,scaled,0.0 - 1.0
6,test6,scaled,0.0 - 1.0
7,test7,scaled,0.0 - 1.0
8,test1,renamed,test1_renamed
9,test3,renamed,test3_regex_renamed
10,test4,renamed,test4_regex_renamed
```

## Thanks

This tool was made possible with [Pandas](https://pandas.pydata.org/), [PyArrow](https://arrow.apache.org/docs/python/index.html), [jsonschema](https://pypi.org/project/jsonschema/), and of course [Python](https://www.python.org/).


  