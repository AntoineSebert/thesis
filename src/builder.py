#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# IMPORTS #############################################################################################################


import logging
from math import lcm
from pathlib import Path

from defusedxml import ElementTree  # type: ignore

from graph_model import App, Graph, Job, Task

from model import Architecture, Configuration, Core, Problem, Processor

from timed import timed_callable


# FUNCTIONS ###########################################################################################################


def _import_arch(filepath: Path) -> Architecture:
	"""Returns an architecture from a architecture file.

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
		arch.append(Processor(int(cpu.get("Id")), set()))
		arch[-1].cores = {Core(int(core.get("Id")), arch[-1]) for core in cpu}

	return set(arch)


def _compute_hyperperiod(apps: list[App]) -> int:
	"""Computes the hyperperiod.

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


def _create_jobs(apps: list[App], hyperperiod: int) -> list[App]:
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
	apps : list[App]
		A list of applications whose tasks have been populated with jobs.
	"""

	for app in apps:
		for task in app:
			for i in range(int(hyperperiod / task.period)):
				task.jobs.add(Job(task, slice(i * task.period, (i * task.period) + task.deadline), set()))

	return apps


def _import_graph(filepath: Path, arch: Architecture) -> Graph:
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
		apps.append(App(app.get("Name"), set()))

		_tasks = [
			Task(node, apps[-1])
			for runnable in app.iter("Runnable") if (node := nodes.get(runnable.get("Name"))) is not None
		]

		if app.get("Inorder") == "true":
			for i, task in enumerate(_tasks[1:]):
				task.child = _tasks[i - 1]

		apps[-1].tasks = set(_tasks)

	hyperperiod = _compute_hyperperiod(apps)

	return Graph(sorted(_create_jobs(apps, hyperperiod), reverse=True), hyperperiod)


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

	arch = _import_arch(config.filepaths.cfg)
	logging.info("Imported architecture from " + config.filepaths.cfg.name)

	graph = _import_graph(config.filepaths.tsk, arch)
	logging.info("Imported graphs from " + config.filepaths.tsk.name)

	return Problem(config, arch, graph)
