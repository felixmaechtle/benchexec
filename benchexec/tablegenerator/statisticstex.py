# This file is part of BenchExec, a framework for reliable benchmarking:
# https://github.com/sosy-lab/benchexec
#
# SPDX-FileCopyrightText: 2007-2020 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0

import copy
import logging
import re
from collections import Counter, defaultdict
from typing import List, Iterable

from benchexec.tablegenerator.columns import Column

from benchexec.tablegenerator import util
from benchexec.tablegenerator.statistics import ColumnStatistics, StatValue

TEX_HEADER = r"""% The following definition defines a command for each value.
% The command name is the concatenation of the first six arguments.
% To override this definition, define \StoreBenchExecResult with \newcommand before including this file.
% Arguments: benchmark name, runset name, column title, column category, column subcategory, statistic, value
\providecommand\StoreBenchExecResult[7]{\expandafter\newcommand\csname#1#2#3#4#5#6\endcsname{#7}}%
"""


class LatexCommand:
    """Data holder for latex command."""

    def __init__(self, benchmark_name="", runset_name=""):
        self.benchmark_name = LatexCommand.format_command_part(str(benchmark_name))
        self.runset_name = LatexCommand.format_command_part(str(runset_name))
        self.column_title = ""
        self.column_category = ""
        self.column_subcategory = ""
        self.stat_type = ""
        self.value = None

    def set_command_part(self, part_name: str, part_value) -> "LatexCommand":
        """Sets the value of the command part

        Available part names:
            benchmark_name, runset_name, column_title, column_category, column_subcategory, stat_type

        Args:
            part_name: One of the names above
            part_value: The value to be set for this command part

        Returns:
            This LatexCommand
        """
        self.__dict__[part_name] = LatexCommand.format_command_part(str(part_value))
        return self

    def set_command_value(self, value: str) -> "LatexCommand":
        """Sets the value for this command

        The value must be formatted. No checks are made in this method.
        It will be converted to string.

        Args:
            value: The new command value
        Returns:
            This LatexCommand
        """
        if value is None:
            value = ""
        self.value = str(value)
        return self

    def to_latex_raw(self) -> str:
        """Prints latex command with raw value (e.g. only number, no additional latex command)."""
        return self._get_command_formatted(self.value)

    def __repr__(self):
        return "\\StoreBenchExecResult{%s}{%s}{%s}{%s}{%s}{%s}" % (
            self.benchmark_name,
            self.runset_name,
            self.column_title,
            self.column_category,
            self.column_subcategory,
            self.stat_type,
        )

    def _get_command_formatted(self, value: str) -> str:
        """Formats the command with all parts and appends the value

        To use a custom format for the value, for example
            \\StoreBenchExecResult{some}{stuff}...{last_name_part}{\\textbf{value}}
        format the value and give it to this function
        """
        if not value:
            value = ""
        return str(self) + "{%s}" % value

    @staticmethod
    def format_command_part(name: str) -> str:
        name = re.sub(
            "^[1-9]+$", lambda match: util.number_to_roman_string(match.group()), name
        )

        name = re.split("[^a-zA-Z]", name)

        name = "".join(util.cap_first_letter(word) for word in name)

        return name


def write_tex_command_table(
    out,
    run_sets: List,
    stats: List[List[ColumnStatistics]],
    **kwargs,
):
    # Saving the formatted benchmarkname and niceName with the id of the runset to prevent latter formatting
    formatted_names = {}
    for run_set in run_sets:
        benchmark_name_formatted = LatexCommand.format_command_part(
            run_set.attributes["benchmarkname"]
        )
        runset_name_formatted = LatexCommand.format_command_part(
            run_set.attributes["niceName"]
        )
        formatted_names[id(run_set)] = benchmark_name_formatted, runset_name_formatted

    # Counts the total number of benchmarkname and niceName combinations
    names_total_counts = Counter(formatted_names.values())

    # Counts the actual used benchmarkname and niceName combinations
    names_already_used = defaultdict(int)

    out.write(TEX_HEADER)
    for run_set, stat_list in zip(run_sets, stats):
        name_tuple = formatted_names[id(run_set)]

        # Increasing the count before the check to add suffix 1 to the first encounter of a duplicated
        # benchmarkname + niceName combination
        names_already_used[name_tuple] += 1
        benchmark_name_formatted, runset_name_formatted = name_tuple

        # Duplication detected, adding suffix to benchmarkname
        if names_total_counts[name_tuple] > 1:
            suffix = util.number_to_roman_string(names_already_used[name_tuple])
            logging.warning(
                'Duplicated formatted benchmark name + runset name "%s" detected. '
                "The combination of names must be unique for Latex. "
                "Adding suffix %s to benchmark name",
                benchmark_name_formatted + runset_name_formatted,
                suffix,
            )
            benchmark_name_formatted += suffix

        command = LatexCommand(benchmark_name_formatted, runset_name_formatted)

        for latex_command in _provide_latex_commands(run_set, stat_list, command):
            out.write(latex_command.to_latex_raw())
            out.write("%\n")


def _provide_latex_commands(
    run_set, stat_list: List[ColumnStatistics], current_command: LatexCommand
) -> Iterable[LatexCommand]:
    """
    Provides all LatexCommands for a given run_set + stat_list combination

    Args:
        run_set: A RunSetResult object
        stat_list: List of ColumnStatistics for each column in run_set
        current_command: LatexCommand with benchmark_name and displayName already filled

    Yields:
        All LatexCommands from the run_set + stat_list combination
    """
    # Preferring the display title over the standard title of a column to allow
    # custom titles defined by the user
    def select_column_name(col):
        return col.display_title if col.display_title else col.title

    column_titles_total_count = Counter(
        select_column_name(column) for column in run_set.columns
    )
    column_titles_already_used = defaultdict(int)

    for column, column_stats in zip(run_set.columns, stat_list):
        column_title = select_column_name(column)

        # Increasing the count before the check to add suffix 1 to the first encounter of a duplicated
        # column title
        column_titles_already_used[column_title] += 1

        if column_titles_total_count[column_title] > 1:
            suffix = util.number_to_roman_string(
                column_titles_already_used[column_title]
            )
            logging.warning(
                'Duplicated formatted column name "%s" detected! '
                "Column names must be unique for Latex. "
                "Adding suffix %s to column for now",
                column_title,
                suffix,
            )
            column_title += suffix

        current_command.set_command_part("column_title", column_title)

        yield from _column_statistic_to_latex_command(
            current_command, column_stats, column
        )


def _column_statistic_to_latex_command(
    init_command: LatexCommand,
    column_statistic: ColumnStatistics,
    column: Column,
) -> Iterable[LatexCommand]:
    """Parses a ColumnStatistics to Latex Commands and yields them

    The provided LatexCommand must have specified benchmark_name, display_name and column_name.

    Args:
        init_command: LatexCommand with not empty benchmark_name and display_name
        column_statistic: ColumnStatistics to convert to LatexCommand
        column: Current column with meta-data
    Yields:
        A completely filled LatexCommand
    """
    if not column_statistic:
        return

    stat_value: StatValue
    for stat_name, stat_value in column_statistic.__dict__.items():
        if stat_value is None:
            continue

        # Copy command to prevent using filled command parts from previous iterations
        command = copy.deepcopy(init_command)

        column_parts = stat_name.split("_")
        if len(column_parts) < 2:
            column_parts.append("")

        # Some colum_categories use _ in their names, that's why the column_category is the
        # whole split list except the last word
        command.set_command_part(
            "column_category",
            "".join(
                util.cap_first_letter(column_part) for column_part in column_parts[0:-1]
            ),
        )
        command.set_command_part("column_subcategory", column_parts[-1])

        for k, v in stat_value.__dict__.items():
            # "v is None" instead of "if not v" used to allow number 0
            if v is None:
                continue
            command.set_command_part("stat_type", k)
            command.set_command_value(column.format_value(value=v, format_target="csv"))
            yield command
        if column.unit:
            command.set_command_part("stat_type", "unit")
            command.set_command_value(column.unit)
            yield command
