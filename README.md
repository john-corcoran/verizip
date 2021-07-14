# Verizip

This repository contains a Python script, and macOS Automator 'Quick Action' workflows containing this script, that provides hash-verified creation of zip archives. Hash values are compared between source files and compressed equivalents within created archives, to ensure that no discrepancies occurred during compression. The Python script is cross-platform (Python 2.7 onwards); the macOS Automator Quick Action workflows allow for integration with Finder.

## Prerequisites

Python 2.7 or later is required. This script has been tested using Python 2.7 on macOS 11.4, Ubuntu 20.04, and Windows 10 20H2.

## Python script usage

Files in one or more source paths will be compressed into a new zip archive, with hash values for source files verified against equivalents for each compressed file after zip creation is complete.

Syntax:

    python verizip.py source_path [source_path ...] [flags]

Usage example:

    python verizip.py gov.archives.arc.1155023 TourTheInternationalSpaceStation

The above will compress all files in folders `gov.archives.arc.1155023` and `TourTheInternationalSpaceStation` into a new zip file which will be created in the working folder (see `-o` below for filename options).

The available flags can be viewed using: `python verizip.py --help`, and are as follows:

- `-o [str]` or `--output [str]`: set the output path for the zip file. If unspecified, the zip will be created in the current working folder, with filename of either `[source_filename_without_extension].zip` (if only one file is being compressed) or `[datetime]_archive.zip` (if multiple files are being compressed).
- `-d` or `--root-directory`: if used, all files within the zip will be placed in a shared parent directory.
- `--ignore-dotfiles`: files and folders beginning with `.` will not be processed (such folders are typically hidden and contain system/settings data).
- `--ignore-windows-volume-folders`: folders named `System Volume Information` and `$RECYCLE.BIN` will not be processed (such folders typically contain hidden Windows system information).

Usage example incorporating flags:

    python verizip.py gov.archives.arc.1155023 TourTheInternationalSpaceStation -o archive.zip -d --ignore-dotfiles --ignore-windows-volume-folders

## macOS Automator usage

To install the Automator Quick Action workflows, download the `.workflow` bundles from this repository and move them to your `~/Library/Services/` folder. Two workflows are provided, to either ignore or include dotfiles.

When installed, within Finder, highlight files you wish to compress then right click and choose one of the Verizip options from the Quick Actions list. The zip file will be created in the folder containing the last item you selected to compress. A system notification from `Script Editor` will display when the script completes.

## Contributing

If you would like to contribute, please fork the repository and use a feature branch. Pull requests are warmly welcome.

## Licensing

The code in this project is licensed under the MIT License.
