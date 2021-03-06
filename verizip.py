#!/usr/bin/env python

"""Verizip: Python 2.7 and macOS Automator compatible creation of hash-verified zip files"""

import argparse
import collections
import datetime
import hashlib
import itertools
import logging
import os
import platform
import sys
import zipfile


def _prepare_logging():
    """Prepare and return logging object to be used throughout script"""
    log = logging.getLogger(__name__)
    log.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    log.addHandler(console_handler)
    return log


def check_all_iterable_values_equal(iterable):
    """Check all items of an iterable are the same value"""
    return all(second_value_onwards == iterable[0] for second_value_onwards in iterable[1:])


def get_common_root_directory(paths, sep):
    """Return string with root path that is common to provided list of paths"""
    directory_levels_tuple = zip(*[p.split(sep) for p in paths])
    common_directory = sep.join(
        x[0] for x in itertools.takewhile(check_all_iterable_values_equal, directory_levels_tuple)
    )
    if common_directory:
        return common_directory
    else:
        return None


def get_missing_sources(source_paths, files_only=False):
    """Return list of any source paths that aren't a file or a folder"""
    missing_sources = [
        source_path
        for source_path in source_paths
        if (not os.path.isdir(source_path) or files_only) and not os.path.isfile(source_path)
    ]
    return missing_sources


def get_list_as_str(list_to_convert):
    """Convert list into comma separated string, with each element enclosed in single quotes"""
    return ", ".join(["'{}'".format(list_item) for list_item in list_to_convert])


def bytes_filesize_to_readable_str(bytes_filesize):
    """Convert bytes integer to kilobyte/megabyte/gigabyte/terabyte equivalent string"""
    if bytes_filesize < 1024:
        return "{} B"
    num = float(bytes_filesize)
    for unit in ["B", "KB", "MB", "GB"]:
        if abs(num) < 1024.0:
            return "{:.1f} {}".format(num, unit)
        num /= 1024.0
    return "{:.1f} {}".format(num, "TB")


def printer(message, level, display_on_mac=False):
    """Either show macOS notification or print message to console, depending on OS"""
    log = logging.getLogger(__name__)
    if check_running_from_automator() and display_on_mac:
        os.system(
            """
            osascript -e 'display notification "{}" with title "{}"'
            """.format(
                message, "Verizip"
            )
        )
    else:
        getattr(log, level)(message)


def add_files_to_zip(
    file_list, common_root_directory, zip_handler, put_all_files_in_shared_root_dir
):
    """Add files referenced in file path list to a zip file"""
    for file_path in file_list:
        rel_path = file_path
        if common_root_directory is not None:
            rel_path = os.path.relpath(file_path, common_root_directory)
        else:
            # If we don't have a common root dir then, on Windows, path will begin with drive letter
            # e.g. 'C:\' - remove this for adding to the ZIP
            if platform.system() == "Windows":
                rel_path = rel_path.replace(":", "")
        try:
            if put_all_files_in_shared_root_dir and common_root_directory is not None:
                zip_handler.write(
                    file_path,
                    arcname=os.path.join(os.path.basename(common_root_directory), rel_path),
                )
            else:
                zip_handler.write(file_path, arcname=rel_path)
        except IOError:
            printer(
                "'{}' no longer present in folder - zip creation aborted".format(file_path),
                "error",
                True,
            )
            raise
        except OSError:
            printer("OSError on '{}' - zip creation aborted".format(file_path), "error", True)
            raise


def get_file_paths_and_size(paths, ignore_dotfiles, ignore_windows_volume_folders):
    """Get list of file paths at a path (recurses subdirectories) and total size of directory"""

    def walk_error(os_error):
        """Print user warning and raise OSError"""
        printer("Cannot access '{}'; zip creation aborted".format(os_error.filename), "error", True)
        raise os_error

    EXCLUDE_FOLDERS = {"$RECYCLE.BIN", "System Volume Information"}
    exclude_folder_seen_log = {}  # type: typing.Dict[str, typing.List[str]]
    files = []
    size = 0
    for path in sorted(paths):
        for root, dirs, filenames in os.walk(path, onerror=walk_error):
            if ignore_dotfiles:
                filenames = [f for f in filenames if not f[0] == "."]
                dirs[:] = [d for d in dirs if not d[0] == "."]
            if ignore_windows_volume_folders:
                for directory in [d for d in dirs if d in EXCLUDE_FOLDERS]:
                    if directory not in exclude_folder_seen_log:
                        exclude_folder_seen_log[directory] = []
                        exclude_folder_seen_log[directory].append(os.path.join(root, directory))
                        printer(
                            "'{}' will not be processed (Windows system directory)".format(
                                os.path.join(root, directory)
                            ),
                            "info",
                        )
                    else:
                        exclude_folder_seen_log[directory].append(os.path.join(root, directory))
                        printer(
                            "Excluded folder '{}' has been excluded more than once within path"
                            " '{}' - this is unexpected, as this folder should only be found in"
                            " the root of a drive. Be advised that the following folders will"
                            " NOT be processed: {}".format(
                                directory,
                                path,
                                get_list_as_str(exclude_folder_seen_log[directory]),
                            ),
                            "warning",
                        )
                dirs[:] = [d for d in dirs if not d in EXCLUDE_FOLDERS]
            for name in filenames:
                files.append(os.path.join(root, name))
                size += os.path.getsize(os.path.join(root, name))
    return sorted(files), size


def hash_file_at_path(file_path, algorithm="sha1"):
    """Return str containing lowercase hash value of file at a file path"""
    block_size = 64 * 1024
    hasher = getattr(hashlib, algorithm)()
    with open(file_path, "rb") as file_handler:
        while True:
            data = file_handler.read(block_size)
            if not data:
                break
            hasher.update(data)
    return hasher.hexdigest()


def hash_file_in_zip(zip_handler, file_path_in_zip, algorithm="sha1"):
    """Return str containing lowercase hash value of file within a zip archive"""
    block_size = 64 * 1024
    hasher = getattr(hashlib, algorithm)()
    with zip_handler.open(file_path_in_zip, "r") as file_handler:
        while True:
            data = file_handler.read(block_size)
            if not data:
                break
            hasher.update(data)
    return hasher.hexdigest()


def get_hash_dict(file_list, root_dir, dir_flag):
    """Return a dictionary of hash values for files at provided file paths"""
    hash_dict = {}
    for file_path in file_list:
        if not os.path.isfile(file_path):
            printer(
                "'{}' has either been deleted or is not a regular file (may be a pipe/socket) - zip"
                " creation aborted".format(file_path),
                "error",
                True,
            )
            raise IOError(
                "'{}' has either been deleted or is not a regular file (may be a pipe/socket) - zip"
                " creation aborted".format(file_path)
            )
        try:
            hash_value = hash_file_at_path(file_path)
        except IOError:
            printer(
                "'{}' no longer present in folder - zip creation aborted".format(file_path),
                "error",
                True,
            )
            raise
        except OSError:
            printer("OSError on '{}' - zip creation aborted".format(file_path), "error", True)
            raise
        if hash_value not in hash_dict:
            hash_dict[hash_value] = []
        if root_dir is not None:
            rel_path = os.path.relpath(file_path, root_dir)
        else:
            rel_path = file_path
            if platform.system() != "Windows":
                rel_path = rel_path[1:]  # Remove leading slash for Linux / Mac
            else:
                rel_path = rel_path.replace(":", "")  # Remove ':' for e.g. 'C:\'
        if dir_flag and root_dir is not None:
            rel_path = os.path.join(os.path.basename(root_dir), rel_path)
        if platform.system() == "Windows":
            rel_path = rel_path.replace("\\", "/")  # Standardise path format if on Windows
        hash_dict[hash_value].append(rel_path)
    return hash_dict


def get_safe_file_path(file_path):
    """If a file already exists at path, get a similar new file path instead"""
    file_basename_noext = os.path.splitext(os.path.basename(file_path))[0]
    filename_suffix = 2
    while os.path.isfile(file_path):
        file_path = os.path.join(
            os.path.dirname(file_path),
            "{}_{}{}".format(
                file_basename_noext,
                filename_suffix,
                os.path.splitext(file_path)[1],
            ),
        )
        filename_suffix += 1
    return file_path


def check_running_from_automator():
    """Return True if script is running as part of macOS Automator"""
    if (
        platform.system() == "Darwin"
        and os.environ.get("XPC_SERVICE_NAME") == "com.apple.automator.xpc.runner"
    ):
        return True
    return False


def create_zip(
    output_path,
    input_paths,
    ignore_dotfiles,
    ignore_windows_volume_folders,
    put_all_files_in_shared_root_dir,
    path_separator,
):
    """Create zipfile and return file hash info for subsequent verification"""
    # Hash each file, add hashes to file_hash_dict, then add to zip
    file_hash_dict = {}
    total_file_count = 0
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as zip_handler:
        for path in input_paths:
            if len(input_paths) == 1:
                common_root_directory = os.path.dirname(path)
            else:
                common_root_directory = get_common_root_directory(input_paths, path_separator)
            if os.path.isdir(path):
                file_list, total_size = get_file_paths_and_size(
                    [path], ignore_dotfiles, ignore_windows_volume_folders
                )
                printer(
                    "'{}' contains {} files ({}) for compression".format(
                        path, len(file_list), bytes_filesize_to_readable_str(total_size)
                    ),
                    "info",
                )
                total_file_count += len(file_list)
                directory_hash_dict = get_hash_dict(
                    file_list,
                    common_root_directory,
                    put_all_files_in_shared_root_dir,
                )
                for hash_value, relative_paths in directory_hash_dict.items():
                    if hash_value not in file_hash_dict:
                        file_hash_dict[hash_value] = relative_paths
                    else:
                        file_hash_dict[hash_value].extend(relative_paths)
                add_files_to_zip(
                    file_list,
                    common_root_directory,
                    zip_handler,
                    put_all_files_in_shared_root_dir,
                )
                printer("'{}' contents added to zip successfully".format(path), "info")
            else:
                total_file_count += 1
                individual_file_hash_dict = get_hash_dict(
                    [path],
                    common_root_directory,
                    put_all_files_in_shared_root_dir,
                )
                for hash_value, relative_paths in individual_file_hash_dict.items():
                    if hash_value not in file_hash_dict:
                        file_hash_dict[hash_value] = relative_paths
                    else:
                        file_hash_dict[hash_value].extend(relative_paths)
                add_files_to_zip(
                    [path],
                    common_root_directory,
                    zip_handler,
                    put_all_files_in_shared_root_dir,
                )
                printer("'{}' added to zip successfully".format(path), "info")
    return file_hash_dict, total_file_count


def main():
    """Capture arguments, get hashes for local files, create zip, and check hashes for compressed
    files within zip match equivalents for local files

    """
    run_time_str = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log = _prepare_logging()
    Args = collections.namedtuple(
        "Args",
        (
            "input_paths",
            "output_path",
            "root_directory",
            "ignore_dotfiles",
            "ignore_windows_volume_folders",
        ),
    )
    # If we are running from Mac Automator, take file paths from sys.argv
    if check_running_from_automator():
        # Example sys.argv for two files selected: ['-c', '/absolute/path/1.txt',
        # '/absolute/path/to/2.txt']
        args = Args(
            input_paths=sys.argv[1:],
            output_path=None,
            root_directory=False,
            ignore_dotfiles=False,
            ignore_windows_volume_folders=False,
        )
    # Otherwise, use argparse and allow for some additional options
    else:
        parser = argparse.ArgumentParser()
        parser.add_argument("input_paths", nargs="+", help="Items to compress")
        parser.add_argument("-o", "--output_path", "--output", help="Filename for zip")
        parser.add_argument(
            "-d",
            "--root-directory",
            action="store_true",
            help="Place all files in zip within a shared parent folder",
        )
        parser.add_argument(
            "--ignore-dotfiles",
            action="store_true",
            help="Ignore files and folders beginning with '.' (typically these are hidden folders)",
        )
        parser.add_argument(
            "--ignore-windows-volume-folders",
            action="store_true",
            help=(
                "Ignore folders named 'System Volume Information' and '$RECYCLE.BIN' (typically"
                " these contain hidden system information)"
            ),
        )

        parsed_args = parser.parse_args()
        args = Args(**vars(parsed_args))

    # Check passed arguments and return if issues
    if get_missing_sources(args.input_paths):
        printer(
            "Path(s) {} not found".format(get_list_as_str(get_missing_sources(args.input_paths))),
            "error",
            True,
        )
        return

    # Set path separator based on OS
    if platform.system() == "Windows":
        path_separator = "\\"
    else:
        path_separator = "/"

    # Convert input paths into absolute paths
    input_paths = [os.path.abspath(path) for path in args.input_paths]

    # Set output path
    if args.output_path is not None:
        output_path = args.output_path
        output_directory = os.path.dirname(output_path)
    else:
        if check_running_from_automator():
            # Last item in the list of arguments will be the last item clicked in Finder
            output_directory = os.path.dirname(input_paths[-1])
        else:
            output_directory = "."
        if len(input_paths) == 1:
            output_filename = os.path.basename("{}.zip".format(input_paths[0]))
        else:
            output_filename = "{}_archive.zip".format(run_time_str)
        output_path = get_safe_file_path(os.path.join(output_directory, output_filename))
    printer("Zip file will be created at path '{}'".format(output_path), "info")

    # Create zipfile and get file_hash_dict info for subsequent verification
    try:
        file_hash_dict, total_file_count = create_zip(
            output_path,
            input_paths,
            args.ignore_dotfiles,
            args.ignore_windows_volume_folders,
            args.root_directory,
            path_separator,
        )
    except:
        # Log the exception to a file, so we can view later if running from Automator
        error_log_file_path = os.path.join(
            output_directory, "{}_verizip_error.txt".format(run_time_str)
        )
        error_log_handler = logging.FileHandler(error_log_file_path)
        error_log_handler.setLevel(logging.ERROR)
        error_log_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        )
        log.addHandler(error_log_handler)
        log.exception("Exception occurred during creation of zip file '%s':", output_path)
        printer(
            "Error occurred - see '{}'".format(os.path.abspath(error_log_file_path)), "error", True
        )
        if os.path.isfile(output_path):
            os.remove(output_path)
        return
    printer("'{}' finalised - will now be verified".format(output_path), "info")

    # Get hashes of files within finalised zip
    zip_hash_dict = {}
    with zipfile.ZipFile(output_path, "r") as zip_handler:
        zip_file_listing = zip_handler.namelist()
        zip_file_count = 0
        for file_within_zip in zip_file_listing:
            # Todo: confirm no 'file_info.is_dir()' type check needed here - don't believe so, as
            # only files with paths are being added, rather than directories as separate archive
            # items
            zip_file_count += 1
            hash_value = hash_file_in_zip(zip_handler, file_within_zip)
            if hash_value not in zip_hash_dict:
                zip_hash_dict[hash_value] = []
            zip_hash_dict[hash_value].append(file_within_zip)

    # Verify that hashes from source files match those for compressed files within newly-created zip
    if file_hash_dict == zip_hash_dict and total_file_count == zip_file_count:
        printer("Verification complete; no discrepancies identified", "info")
        printer("'{}' created successfully".format(output_path), "info", True)
    else:
        error_log_file_path = os.path.join(
            output_directory, "{}_verizip_error.txt".format(run_time_str)
        )
        with open(error_log_file_path, "w") as error_log_file_handler:
            for hash_value, file_paths in file_hash_dict.items():
                if hash_value not in zip_hash_dict:
                    error_log_file_handler.write(
                        "Hash '{}' not present in zip file (with expected files {})\n".format(
                            hash_value, get_list_as_str(file_paths)
                        )
                    )
                elif sorted(file_paths) != sorted(zip_hash_dict[hash_value]):
                    error_log_file_handler.write(
                        "Files for hash '{}' do not match between source and zip ({} in source - {}"
                        " in zip)\n".format(hash_value, file_paths, zip_hash_dict[hash_value])
                    )
        printer(
            "'{}' failed verification - see error log at '{}'".format(
                output_path, os.path.abspath(error_log_file_path)
            ),
            "error",
            True,
        )
        os.remove(output_path)  # Delete the zip that failed verification


if __name__ == "__main__":
    # Entry point when running script directly
    main()
