#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# IMPORTS #############################################################################################################


import logging
from math import lcm
from pathlib import Path

from arch_model import Architecture, Core, Processor

from defusedxml import ElementTree  # type: ignore

from graph_model import App, Criticality, Graph, Job, Task

from model import Configuration, Problem

from sortedcontainers import SortedSet  # type: ignore

from timed import timed_callable


# FUNCTIONS ###########################################################################################################


def _print_jobs(graph: Graph) -> None:
	"""Prints the jobs for all tasks.

	Parameters
	----------
	graph : Graph
		An app graph.
	"""

	for app in graph:
		for task in app:
			for job in task:
				print(job.pformat())


def _import_arch(filepath: Path) -> Architecture:
	"""Returns an architecture extracted from a architecture file.

	Parameters
	----------
	filepath : Path
		A `Path` to a *.cfg* file representing the processor architecture.

	Returns
	-------
	Architecture
		An set of `Processor`.
	"""

	arch: list[Processor] = []

	for cpu in ElementTree.parse(filepath).iter("Cpu"):
		arch.append(Processor(int(cpu.get("Id"))))
		arch[-1].cores = {Core(int(core.get("Id")), arch[-1]) for core in cpu}

	return set(arch)


def _compute_hyperperiod(apps: list[App]) -> int:
	"""Computes the hyperperiod from a list of apps.

	Parameters
	----------
	apps : list[App]
		Applications to compute a hyperperiod for.

	Returns
	-------
	int
		The hyperperiod for the apps.
	"""

	periods = {task.period for app in apps for task in app}

	return lcm(*periods)


def _create_jobs(apps: list[App], hyperperiod: int) -> SortedSet[App]:
	"""Create the jobs for the tasks in all applications.
	If local hyperperiods were to be implemented, this step should be moved at the end of the initial mapping.

	Parameters
	----------
	apps : list[App]
		A list of applications.
	hyperperiod : int
		A hyperperiod.

	Returns
	-------
	apps : SortedSet[App]
		A set of applications whose tasks have been populated with jobs.
	"""

	for app in apps:
		for task in app:
			for i in range(int(hyperperiod / task.period)):
				start = i * task.period
				window = slice(start, start + task.deadline)
				task.jobs.add(Job(task, window, window))

	return apps


def _import_graph(filepath: Path) -> Graph:
	"""Creates the graph from the tasks file, then returns it.

	Parameters
	----------
	filepath : Path
		A `Path` to a *.tsk* file representing the task graph.

	Returns
	-------
	Graph
		An app graph.
	"""

	et = ElementTree.parse(filepath)
	nodes = {node.get("Name"): node for node in et.iter("Node")}
	apps: list[App] = []

	for app in et.iter("Application"):
		apps.append(App(app.get("Name"), False))

		tasks = [
			Task(
				int(node.get("Id")),
				apps[-1],
				int(node.get("WCET")),
				int(node.find("Period").get("Value")),
				int(node.get("Deadline")),
				Criticality(int(node.get("CIL"))),
			) for runnable in app.iter("Runnable") if (node := nodes.get(runnable.get("Name"))) is not None
		]

		if app.get("Inorder") == "true":
			apps[-1].order = True

			for i, task in enumerate(tasks[1:]):
				task.parent = tasks[i]

		apps[-1].tasks = tasks

	hyperperiod = _compute_hyperperiod(apps)

	return Graph(_create_jobs(apps, hyperperiod), hyperperiod)


# ENTRY POINT #########################################################################################################


@timed_callable("Building the problem...")
def build(config: Configuration) -> Problem:
	"""Creates an internal representation for a problem.

	Parameters
	----------
	config : Configuration
		A configuration for the scheduling problem.

	Returns
	-------
	Problem
		A `Problem` generated from the test case.
	"""

	cfg = config.filepaths.cfg
	tsk = config.filepaths.tsk

	arch = _import_arch(cfg)
	logging.info("Imported architecture from " + cfg.name)

	graph = _import_graph(tsk)
	logging.info("Imported graphs from " + tsk.name)

	# _print_jobs(graph)

	return Problem(config, arch, graph)
