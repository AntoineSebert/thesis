#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# IMPORTS #############################################################################################################


import logging
from pathlib import Path
from weakref import ref
from typing import Iterable

from model import Architecture, Core, FilepathPair, App, Task, Problem, Processor
from timed import timed_callable

from defusedxml import ElementTree


# FUNCTIONS ###########################################################################################################


def _import_arch(filepath: Path) -> Architecture:
	"""Create the processor architecture from the configuration file, then returns it.

	Parameters
	----------
	filepath : Path
		A `Path` to a *.cfg* file describing the processor architecture.

	Returns
	-------
	Architecture
		An iterable of `Processor`.
	"""

	return [
		Processor(
			i,
			[
				Core(
					ii,
					int(core.get("MacroTick")) if int(core.get("MacroTick")) != 9999999 else None,
					0.0,
					[],
				) for ii, core in enumerate(sorted(cpu, key=lambda e: int(e.get("Id"))))
			]
		) for i, cpu in enumerate(sorted(ElementTree.parse(filepath).iter("Cpu"), key=lambda e: int(e.get("Id"))))
	]


def _import_graph(filepath: Path, arch: Architecture) -> Iterable[App]:
	"""Creates the graph from the tasks file, then returns it.

	Parameters
	----------
	filepath : Path
		A `Path` to a *.tsk* file describing the task graph.

	Returns
	-------
	Graph
		An iterable of `Node`.
	"""

	et = ElementTree.parse(filepath)
	nodes = {node.get("Name"): node for node in et.iter("Node")}
	apps = []

	for app in et.iter("App"):
		tasks = [
			Task(
				int(nodes.get(runnable.get("Name")).get("Id")),
				int(nodes.get(runnable.get("Name")).get("WCET")),
				int(nodes.get(runnable.get("Name")).get("Period")),
				int(nodes.get(runnable.get("Name")).get("Deadline")),
				int(nodes.get(runnable.get("Name")).get("MaxJitter"))
				if nodes.get(runnable.get("Name")).get("MaxJitter") != "-1" else None,
				int(nodes.get(runnable.get("Name")).get("EarliestActivation")),
				ref(arch.get(int(nodes.get(runnable.get("Name")).get("CpuId")))),
				int(nodes.get(runnable.get("Name")).get("CIL"))
			) for runnable in app.iter("Runnable")
		]

		if app.get("Inorder") == "true":
			for i, task in enumerate(tasks[1:]):
				task.child = ref(tasks[i - 1])

		apps.append(App(app.get("Name"), tasks))

	return apps


# ENTRY POINT #########################################################################################################


@timed_callable("Building the problem...")
def build(filepath_pair: FilepathPair) -> Problem:
	"""Creates an internal representation for a problem.

	Parameters
	----------
	filepath_pair : FilepathPair
		A `FilepathPair` pointing to the `*.tsk` and `*.cfg` files.

	Returns
	-------
	Problem
		A `Problem` generated from the test case.
	"""

	arch = _import_arch(filepath_pair.cfg)
	logging.info("Imported architecture from " + filepath_pair.cfg.name)

	graph = _import_graph(filepath_pair.tsk, arch)
	logging.info("Imported graphs from " + filepath_pair.tsk.name)

	return Problem(filepath_pair, graph, arch)
