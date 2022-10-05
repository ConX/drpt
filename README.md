# Data Release Preparation Tool

<!-- @import "[TOC]" {cmd="toc" depthFrom=1 depthTo=6 orderedList=false} -->

<!-- code_chunk_output -->

- [Data Release Preparation Tool](#data-release-preparation-tool)
  - [Description](#description)
  - [Recipes Definition](#recipes-definition)
    - [Overview](#overview)
    - [Actions](#actions)
      - [_drop_](#drop)
      - [_rename_](#rename)
      - [_obfuscate_](#obfuscate)
      - [_no-scaling_](#no-scaling)
  - [Usage](#usage)
  - [Example](#example)
  - [Thanks](#thanks)

<!-- /code_chunk_output -->


> :warning: This is currently at beta development stage and likely has a lot of bugs. Please use the [issue tracker](https://github.com/ConX/drpt/issues) to report an bugs or feature requests.

## Description

Command-line tool for preparing a dataset for publishing by dropping, renaming, scaling, and obfuscating columns defined in a recipe.

After performing the operations defined in the recipe the tool generates the transformed dataset version and a CSV report listing the performed actions.

## Recipes Definition

### Overview

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
  - Column scaling, where by default all columns are Min/Max scaled, except those excluded (`no-scaling`)

All column definitions above support [regular expressions](https://docs.python.org/3/library/re.html#regular-expression-syntax).

### Actions

#### _drop_

The `drop` action is defined as a list of column names to be dropped.

#### _rename_

The `rename` action is defined as a list of objects whose key is the original name (or regular expression), and their value is the target name. When the target uses matched groups from the regular expression those can be provided with their group number prepended with an escaped backslash (`\\1`) [see [example](#example) below].

```json
{
  //...
  "rename": [{"original_name": "target_name"}]
  //...
}
```

#### _obfuscate_

The `obfuscate` action is defined as a list of column names to be obfuscated. 

#### _no-scaling_

By default, the tool Min/Max scales all numerical columns unless the `--no-scaling` command line option is provided. If scaling must be disabled for only a set of columns these columns can be defined using the `no-scaling` action, as a list of column names.


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

## Example

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
```csv
,action,column,details
0,recipe_version,,1.0
1,drpt_version,,0.2.3
2,DROP,test2,
3,DROP,test8,
4,DROP,test9,
5,OBFUSCATE,test3,
6,SCALE_DEFAULT,test1,"[1.1,3.3]"
7,SCALE_DEFAULT,test5,"[0.1,1.0]"
8,SCALE_DEFAULT,test6,"[0.0,5.0]"
9,SCALE_DEFAULT,test7,"[-1.0,2.5]"
10,SCALE_DEFAULT,foo.bar.test,"[1,4]"
11,SCALE_DEFAULT,foo.bar.test2,"[1,4]"
12,RENAME,test1,test1_renamed
13,RENAME,test3,test3_regex_renamed
14,RENAME,test4,test4_regex_renamed
15,RENAME,foo.bar.test,foo_1
16,RENAME,foo.bar.test2,foo_2
```

## Thanks

This tool was made possible with [Pandas](https://pandas.pydata.org/), [PyArrow](https://arrow.apache.org/docs/python/index.html), [jsonschema](https://pypi.org/project/jsonschema/), and of course [Python](https://www.python.org/).


  