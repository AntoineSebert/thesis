#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# IMPORTS #############################################################################################################


from enum import Enum, unique
from functools import partial
from json import JSONEncoder, dumps
from queue import PriorityQueue
from typing import Any
from xml.etree.ElementTree import Element, SubElement, dump, fromstringlist, indent, register_namespace, tostring

from model import Path, Slice, Solution

from timed import timed_callable


# CLASSES #############################################################################################################


class SolutionEncoder(JSONEncoder):
	"""An encoder dedicated to parse `Solution` objects into JSON.

	Methods
	-------
	default(obj)
		The JSON representation of the `Solution`.
	"""

	def default(self: JSONEncoder, obj: Any) -> Any:
		if isinstance(obj, PriorityQueue):
			return [obj.qsize(), obj.empty()]
		elif isinstance(obj, Solution):
			return {"schedule": {
				"configuration": obj.config.json(),
				"hyperperiod": obj.hyperperiod,
				"score": obj.score,
				"mapping": obj.mapping,
			}}
		elif isinstance(obj, Path):
			return str(obj)

		return JSONEncoder.default(self, obj)  # Let the base class default method raise the TypeError


# FUNCTIONS ###########################################################################################################


@timed_callable("Formatting the solutions to JSON...")
def _json_format(solution: Solution) -> str:
	"""Formats a solution into JSON.

	Parameters
	----------
	solution : Solution
		A `Solution`.

	Returns
	-------
	str
		A `str` representing a JSON `Solution`.
	"""
	print(dumps(solution, skipkeys=True, sort_keys=True, indent=4, cls=SolutionEncoder))

	return dumps(solution, skipkeys=True, sort_keys=True, indent=4, cls=SolutionEncoder)


@timed_callable("Formatting the solutions to XML...")
def _xml_format(solution: Solution) -> str:
	"""Formats a solution into a custom XML schema.
	<scheduling>
		<config policy="" switch-time=0 objective="">
			<files tsk="" tsk="" />
		</config>
		<mapping hyperperoid=0 score=0>
			<cpu id=0>
				<core id=0>
					<slice start=0 stop=0 duration=0 app=0 task=0 />
				</core>
			</cpu>
		</mapping>
	</scheduling>

	Parameters
	----------
	solution : Solution
		A `Solution`.

	Returns
	-------
	str
		A `str` representing a XML `Solution`.
	"""

	scheduling = Element("scheduling")
	config = SubElement(scheduling, "configuration", {
		"policy": solution.config.policy,
		"switch-time": str(solution.config.switch_time),
		"objective": "0",  # solution.config.objective,
	})
	config.append(Element("files", {
		"tsk": str(solution.config.filepaths.tsk),
		"cfg": str(solution.config.filepaths.cfg),
	}))

	mapping = SubElement(scheduling, "mapping", {
		"hyperperiod": str(solution.hyperperiod),
		"score": str(solution.score),
	})

	cpus: dict[int, dict[int, list[Slice]]] = {}

	for core, slices in solution.mapping.items():
		if core().processor().id in cpus:
			cpus[core().processor().id][core().id] = slices
		else:
			cpus[core().processor().id] = {core().id: slices}

	for cpu_id, cores in cpus.items():
		cpu = SubElement(mapping, "processor", {"id": f"cpu-{cpu_id}"})
		for core_id, slices in cores.items():
			core = SubElement(cpu, "core", {"id": f"core-{core_id}"})
			core.extend([
				Element("slice", {
					"start": str(_slice.start),
					"stop": str(_slice.stop),
					"duration": str(_slice.stop - _slice.start),
					"app": _slice.task().app().name,
					"task": str(_slice.task().id),
				}) for _slice in slices
			])

	indent(scheduling, space="\t")
	dump(scheduling)

	return tostring(scheduling, encoding="unicode", xml_declaration=True)


@timed_callable("Formatting the solution to a raw string representation...")
def _raw_format(solution: Solution) -> str:
	"""Formats a solution into string.

	Parameters
	----------
	solution : Solution
		A `Solution`.

	Returns
	-------
	str
		A `str` representing a `Solution` object.
	"""

	return str(solution)


@timed_callable("Formatting the solution to SVG...")
def _svg_format(solution: Solution) -> str:
	"""Formats a solution into SVG.

	Parameters
	----------
	solution : Solution
		A `Solution`.

	Returns
	-------
	str
		A `str` representing a SVG `Solution`.
	"""

	register_namespace("", "http://www.w3.org/2000/svg")

	title = "Solution for " + str(solution.config.filepaths.tsk)

	svg = fromstringlist([
		"<svg xmlns='http://www.w3.org/2000/svg' xmlns:xlink='http://www.w3.org/1999/xlink' width='100%' height='100%' lang='en' version='1.1'>",
			f"<title>{title}</title>",
			"<desc>An horizontal chart bar showing the solution to the scheduling problem.</desc>",
			"<style>",  # https://www.w3.org/TR/SVG2/styling.html
			"</style>",
			"<defs>",
				"<symbol id='cpu' class='cpu'>",
					"<text>CPU</text>",
					"<g class='cores'></g>",
				"</symbol>",
				"<symbol id='core' class='core'>",
					"<text>CORE</text>",
					"<g class='slices'></g>",
					"<path y1='0' x1='0' y2='10' x2='10' />",
					"<marker></marker>",  # <circle cx="6" cy="6" r="3" fill="white" stroke="context-stroke" stroke-width="2"/>
				"</symbol>",
				"<symbol id='slice' class='slice'>",
					"<text>SLICE</text>",
					"<text>start</text>",
					"<text>end</text>",
					"<rect x='100' y='100' width='400' height='200' rx='50' fill='green' />",
				"</symbol>",
				"<linearGradient id='background' y2='100%'>",
					"<stop offset='5%' stop-color='rgba(3,126,243,1)' />",
					"<stop offset='95%' stop-color='rgba(48,195,158,1)' />",
				"</linearGradient>",
			"</defs>",
			"<rect fill='url(#background)' x='0' y='0' width='100%' height='100%' />",
			f"<text x='30%' y='10%'>{title}</text>",
			"<g></g>",
		"</svg>",
	])

	return tostring(svg, encoding="unicode")


# CLASSES #############################################################################################################

@unique
class OutputFormat(Enum):
	"""An enumeratino those purpose it to map format keywords to formatting functions.

	Attributes
	----------
	xml : partial
		Callable object mapped to a XML formatter (custom module format).
	json : partial
		Callable object mapped to a JSON formatter.
	raw : partial
		Callable object mapped to a raw formatter (`solution` is converted into a `str`).
	svg : partial
		Callable object mapped to the raw formatter (`solution` is converted into a `str`).

	Methods
	-------
	__call__
		Converts the enumeration member into the corresponding function call.
	"""

	xml: partial = partial(_xml_format)
	json: partial = partial(_json_format)
	raw: partial = partial(_raw_format)
	svg: partial = partial(_svg_format)

	def __call__(self: Any, solution: Solution) -> str:
		"""Converts the enumeratino member into the corresponding function call.

		Parameters
		----------
		solution : Solution
			An `Solution`.

		Returns
		-------
		str
			A `str` representing a `Solution`.
		"""

		return self.value(solution)
