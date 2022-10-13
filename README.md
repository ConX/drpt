# Data Release Preparation Tool

- [Data Release Preparation Tool](#data-release-preparation-tool)
  - [Description](#description)
  - [Installation](#installation)
  - [Usage](#usage)
    - [CLI](#cli)
    - [Recipe Definition](#recipe-definition)
  - [Example](#example)
  - [Thanks](#thanks)

> :warning: This is currently at beta development stage and likely has a lot of bugs. Please use the [issue tracker](https://github.com/ConX/drpt/issues) to report an bugs or feature requests.

## Description

Command-line tool for preparing a dataset for publishing by dropping, renaming, scaling, and obfuscating columns defined in a recipe.

After performing the operations defined in the recipe the tool generates the transformed dataset version and a CSV report listing the performed actions.

## Installation

The tool can be installed using pip:

```shell
pip install drpt
```

## Usage

### CLI

```txt
Usage: drpt [OPTIONS] RECIPE_FILE INPUT_FILE

Options:
  -d, --dry-run           Generate only the report without the release dataset
  -v, --verbose           Verbose [Not implemented]
  -n, --nrows TEXT        Number of rows to read from a CSV file. Doesn't work
                          with parquet files.
  -l, --limits-file PATH  Limits file
  --version               Show the version and exit.
  --help                  Show this message and exit
```

### Recipe Definition

#### Overview
The recipe is a JSON formatted file that includes what operations should be performed on the dataset. For versioning purposes, the recipe also contains a `version` key which is appended in the generated filenames and the report.

**Default recipe:**
```json
{
  "version": "",
  "actions": {
    "drop": [],
    "drop-constant-columns": false,
    "obfuscate": [],
    "disable-scaling": false,
    "skip-scaling": [],
    "rename": []
  }
}
```

The currently supported actions, performed in this order, are as follows:
  - `drop`: Column deletion
  - `drop-constant-columns`: Drops all columns that containt only one unique value
  - `obfuscate`: Column obfuscation, where the listed columns are treated as categorical variables and then integer coded.
  - Scaling: By default all columns are Min/Max scaled
    - `disable-scaling`: Can be used to disable scaling for all columns
    - `skip-scaling`: By default all columns are Min/Max scaled, except those excluded (`skip-scaling`)
  - `rename`: Column renaming

All column definitions above support [regular expressions](https://docs.python.org/3/library/re.html#regular-expression-syntax).

#### Actions

##### _drop_
The `drop` action is defined as a list of column names to be dropped.

##### _drop-constant-columns_
This is a boolean action, which when set to `true` will drop all the columns that have only a single unique value.

##### _obfuscate_
The `obfuscate` action is defined as a list of column names to be obfuscated.

##### _disable-scaling_, _skip-scaling_
By default, the tool Min/Max scales all numerical columns. This behavior can be disabled for all columns by setting the `disable-scaling` action to `true`. If scaling must be disabled for only a set of columns these columns can be defined using the `skip-scaling` action, as a list of column names.

##### _rename_
The `rename` action is defined as a list of objects whose key is the original name (or regular expression), and their value is the target name. When the target uses matched groups from the regular expression those can be provided with their group number prepended with an escaped backslash (`\\1`) [see [example](#example) below].

```json
{
  //...
  "rename": [{"original_name": "target_name"}]
  //...
}
```
## Example

**Input CSV file:**
```csv
test1,test2,test3,test4,test5,test6,test7,test8,test9,foo.bar.test,foo.bar.test2,const
1.1,1,one,2,0.234,0.3,-1,a,e,1,1,1
2.2,2,two,2,0.555,0.4,0,b,f,2,2,1
3.3,3,three,4,0.1,5,1,c,g,3,3,1
2.22,2,two,4,1,0,2.5,d,h,4,4,1
```

**Recipe:**
```json
{
  "version": "1.0",
  "actions": {
    "drop": ["test2", "test[8-9]"],
    "drop-constant-columns": true,
    "obfuscate": ["test3"],
    "skip-scaling": ["test4"],
    "rename": [
      { "test1": "test1_renamed" },
      { "test([3-4])": "test\\1_regex_renamed" },
      { "foo[.]bar[.].*": "foo" }
    ]
  }
}
```

**Generated CSV file:**
```csv
test1_renamed,test3_regex_renamed,test4_regex_renamed,test5,test6,test7,foo_1,foo_2
0.0,0,2,0.1488888888888889,0.06,0.0,0.0,0.0
0.5000000000000001,2,2,0.5055555555555556,0.08,0.2857142857142857,0.3333333333333333,0.3333333333333333
1.0,1,4,0.0,1.0,0.5714285714285714,0.6666666666666666,0.6666666666666666
0.5090909090909091,2,4,1.0,0.0,1.0,1.0,1.0
```

**Report:**
```csv
,action,column,details
0,recipe_version,,1.0
1,drpt_version,,0.2.8
2,DROP,test2,
3,DROP,test8,
4,DROP,test9,
5,DROP_CONSTANT,const,
6,OBFUSCATE,test3,
7,SCALE_DEFAULT,test1,"[1.1,3.3]"
8,SCALE_DEFAULT,test5,"[0.1,1.0]"
9,SCALE_DEFAULT,test6,"[0.0,5.0]"
10,SCALE_DEFAULT,test7,"[-1.0,2.5]"
11,SCALE_DEFAULT,foo.bar.test,"[1,4]"
12,SCALE_DEFAULT,foo.bar.test2,"[1,4]"
13,RENAME,test1,test1_renamed
14,RENAME,test3,test3_regex_renamed
15,RENAME,test4,test4_regex_renamed
16,RENAME,foo.bar.test,foo_1
17,RENAME,foo.bar.test2,foo_2
```

## Thanks

This tool was made possible with [Pandas](https://pandas.pydata.org/), [PyArrow](https://arrow.apache.org/docs/python/index.html), [jsonschema](https://pypi.org/project/jsonschema/), and of course [Python](https://www.python.org/).


  