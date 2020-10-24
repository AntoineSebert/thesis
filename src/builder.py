#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# IMPORTS #############################################################################################################


import logging
from math import lcm
from pathlib import Path
from weakref import ref

from defusedxml import ElementTree  # type: ignore

from model import App, Architecture, Configuration, Core, Graph, Problem, Processor, Task

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

	arch: set[Processor] = []

	for cpu in ElementTree.parse(filepath).iter("Cpu"):
		arch.append(Processor(int(cpu.get("Id")), []))
		arch[-1].cores = [Core(int(core.get("Id")), ref(arch[-1])) for core in cpu]

	return arch


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
		apps.append(App(app.get("Name"), []))

		apps[-1].tasks = [
			Task(node, apps[-1], arch[int(node.get("CpuId"))])
			for runnable in app.iter("Runnable") if (node := nodes.get(runnable.get("Name"))) is not None
		]

		if app.get("Inorder") == "true":
			for i, task in enumerate(apps[-1].tasks[1:]):
				task.child = ref(apps[-1].tasks[i - 1])

	return Graph(sorted(apps, reverse=True), _compute_hyperperiod(apps))


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
