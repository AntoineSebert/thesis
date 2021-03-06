#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# IMPORTS #############################################################################################################


from enum import Enum, unique
from functools import partial
from itertools import accumulate
from json import JSONEncoder, dumps
from queue import PriorityQueue
from typing import Any
from xml.etree.ElementTree import Element, SubElement, dump, indent, register_namespace, tostring

from arch_model import Core, CoreJobMap

from graph_model import Criticality, Job

from model import Path, Solution

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
				"configuration": obj.problem.config.json(),
				"hyperperiod": obj.problem.graph.hyperperiod,
				"score": obj.score,
				"core_jobs": obj.core_jobs,
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

	return dumps(solution, skipkeys=True, sort_keys=True, indent=4, cls=SolutionEncoder)


@timed_callable("Formatting the solutions to XML...")
def _xml_format(solution: Solution) -> str:
	"""Formats a solution into a custom XML schema.
	<scheduling>
		<config algorithm="" switch-time=0 objective="">
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
		"algorithm": solution.problem.config.params.algorithm,
		"switch-time": str(solution.problem.config.params.switch_time),
		"objective": solution.problem.config.params.objective,
	})
	config.append(Element("files", {
		"tsk": str(solution.problem.config.filepaths.tsk),
		"cfg": str(solution.problem.config.filepaths.cfg),
	}))

	mapping = SubElement(scheduling, "mapping", {
		"hyperperiod": str(solution.problem.graph.hyperperiod),
		"score": str(solution.score),
	})

	cpus: dict[int, dict[int, list[Job]]] = {}

	for core, jobs in solution.mapping.items():
		if core.processor.id in cpus:
			cpus[core.processor.id][core.id] = jobs
		else:
			cpus[core.processor.id] = {core.id: jobs}

	for cpu_id, cores in cpus.items():
		cpu = SubElement(mapping, "processor", {"id": f"cpu-{cpu_id}"})
		for core_id, jobs in cores.items():
			_core = SubElement(cpu, "core", {"id": f"core-{core_id}"})
			_core.extend([
				Element("slice", {
					"start": str(job.exec_window.start),
					"stop": str(job.exec_window.stop),
					"duration": str(job.duration),
					"app": job.task.app.name,
					"task": str(job.task.id),
				}) for job in jobs
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


def _draw_scale(g: Element, length: int, x: int, y: int) -> Element:
	"""Creates an XML element representing a scale bar of given length at a given position.
	The big markers are positioned at 0 and every multiple of 1000, and the small ones at every multiple of 100.

	Parameters
	----------
	g : Element
		An XML element to which the scale element will be added.
	length : int
		The length of the scale.
	x, y : int
		The position of the scale.

	Returns
	-------
	g : Element
		An XML element to which the scale bar have been appended.
	"""

	for iii in range(0, int(length / 100)):
		SubElement(g, "line", {
			"x1": str(x + 10 + (iii * 100)), "y1": str(y + 40), "x2": str(x + 10 + (iii * 100)), "y2": str(y + 60),
			"stroke": 'black',
		})

	for iii in range(1, int(length / 1000)):
		SubElement(g, "line", {
			"x1": str(x + 10 + (iii * 1000)), "y1": str(y + 20), "x2": str(x + 10 + (iii * 1000)), "y2": str(y + 80),
			"stroke": 'black',
		})
		SubElement(
			g, "text", {"x": str(x + (iii * 1000) - 10), "y": str(y + 15), "fill": "black"},
		).text = str(iii * 1000)

	SubElement(g, "line", {"x1": str(x + 10), "y1": str(y + 20), "x2": str(x + 10), "y2": str(y + 80), "stroke": 'black'})

	margin = str(x + length + 10)

	SubElement(g, "line", {
		"x1": str(x + 10), "y1": str(y + 50), "x2": margin, "y2": str(y + 50), "stroke": 'black',
	})
	SubElement(g, "line", {"x1": margin, "y1": str(y + 20), "x2": margin, "y2": str(y + 80), "stroke": 'black'})

	return g


def _draw_core(g: Element, core: Core, x: int, y: int, h: int, w: int, hyperperiod: int, mapping: CoreJobMap,
	colors: dict[Criticality, str]) -> Element:
	"""Creates an XML element representing a core, with all the slices scheduled on it.

	Parameters
	----------
	g : Element
		An XML element to which the core element will be added.
	core : Core
		A source core.
	x, y, h, w : int
		The dimensions of the XML element.
	hyperperiod : int
		The hyperperiod.
	mapping : CoreJobMap
		A mapping of cores to a set of jobs.
	colors : dict[Criticality, str]
		A mapping of criticalities to colors.

	Returns
	-------
	g : Element
		An XML element to which the core have been appended.
	"""

	SubElement(g, "rect", {
		"x": str(x), "y": str(y), "height": str(h), "width": str(w),
		"rx": '10',
		"fill": 'white',
		"opacity": "0.8",
	})
	SubElement(g, "text", {"x": str(x + 10), "y": str(y + 20), "fill": "black"}).text = f"core: {core.id}"

	if core in mapping:
		for job in mapping[core]:
			job_info: str = f"period: {job.task.period}\ndeadline: {job.task.deadline}\nwcet: {job.task.wcet}"
			for i, _slice in enumerate(job.execution):
				slice_rect = SubElement(g, "rect", {
					"x": str(x + 10 + _slice.start), "y": str(y + 30),
					"height": "40", "width": str(len(_slice)),
					"rx": '10',
					"fill": colors[job.task.criticality],
					"stroke": "black",
				})
				SubElement(
					slice_rect,
					"title",
				).text = f"App : {job.task.app.name}\n{job_info}\nstart: {job.exec_window.start}\nstop: {job.exec_window.stop}"
				SubElement(
					g, "text", {"x": str(x + 15 + _slice.start), "y": str(y + 90), "fill": "black", "font-size": "smaller"},
				).text = f"T{job.task.id}-J{int(job.sched_window.start / job.task.period) + 1}/{len(job.task)}-S{i + 1}/{len(job.execution)}"

		_draw_scale(g, hyperperiod, x, y)

	return g


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

	hyperperiod = solution.problem.graph.hyperperiod
	arch = solution.problem.arch

	colors: dict[Criticality, str] = {
		Criticality.sta_1: "green",
		Criticality.sta_2: "yellow",
		Criticality.sta_3: "orange",
		Criticality.sta_4: "red",
	}

	title_margin_top = 30

	# core
	core_width = hyperperiod + 20
	core_height = 100
	core_padding_top = 50
	core_margin_top = 20

	# cpu
	cpu_margin_top = title_margin_top + 30
	cpu_height_margin = 60
	cpu_y = list(accumulate(
		(((len(cpu) * (core_height + core_margin_top)) + core_padding_top) + cpu_height_margin for cpu in arch),
		initial=cpu_margin_top,
	))
	cpu_width = core_width + 40
	cpu_x = 30

	core_x = cpu_x + 20

	# img
	img_width = cpu_width + 60
	img_margin_bottom = 40
	img_height = sum(
		((len(cpu) * (core_height + core_margin_top)) + core_padding_top) + cpu_height_margin for cpu in arch
	) + img_margin_bottom

	svg = Element("svg", {"width": str(img_width), "height": str(img_height), "xmlns": 'http://www.w3.org/2000/svg'})

	title = "Solution for " + solution.problem.config.filepaths.tsk.as_posix() + f"; score: {solution.score}, offsets sum: {solution.offset_sum}"

	SubElement(svg, "title").text = title
	SubElement(svg, "desc").text = "An horizontal chart bar showing the solution to the scheduling problem."

	SubElement(svg, "rect", {"fill": 'url(#background)', "x": '0', "y": '0', "width": '100%', "height": '100%'})
	SubElement(
		svg, "text", {"x": '50%', "y": str(title_margin_top), "dominant-baseline": "middle", "text-anchor": "middle"},
	).text = title

	defs = SubElement(svg, "defs")

	gradient = SubElement(defs, "linearGradient", id='background', y2='100%')
	SubElement(gradient, "stop", {"offset": '5%', "stop-color": 'rgba(3,126,243,1)'})
	SubElement(gradient, "stop", {"offset": '95%', "stop-color": 'rgba(48,195,158,1)'})

	g = SubElement(svg, "g")

	for i, cpu in enumerate(arch):
		cpu_height = (len(cpu) * (core_height + core_margin_top)) + core_padding_top
		SubElement(
			g,
			"rect",
			{
				"x": str(cpu_x), "y": str(cpu_y[i]), "width": str(cpu_width), "height": str(cpu_height),
				"rx": '20',
				"fill": 'black',
				"opacity": "0.5",
			},
		)
		SubElement(g, "text", {"x": str(cpu_x + 20), "y": str(cpu_y[i] + 30), "fill": "white"}).text = f"cpu: {cpu.id}"

		core_y = list(accumulate((core_height + core_margin_top for core in cpu), initial=cpu_y[i] + core_padding_top))

		for ii, core in enumerate(cpu):
			_draw_core(g, core, core_x, core_y[ii], core_height, core_width, hyperperiod, solution.core_jobs, colors)

	indent(svg, space="\t")
	_svg = tostring(svg, encoding="unicode", xml_declaration=True)
	#print(_svg)

	return _svg


# CLASSES #############################################################################################################

@unique
class OutputFormat(Enum):
	"""An enumeration those purpose it to map format keywords to formatting functions.

	Attributes
	----------
	xml : partial
		Callable object mapped to a XML formatter (custom module format).
	json : partial
		Callable object mapped to a JSON formatter.
	svg : partial
		Callable object mapped to the raw formatter (`solution` is converted into a `str`).
	raw : partial
		Callable object mapped to a raw formatter (`solution` is converted into a `str`).

	Methods
	-------
	__call__
		Converts the enumeration member into the corresponding function call.
	"""

	xml: partial = partial(_xml_format)
	json: partial = partial(_json_format)
	svg: partial = partial(_svg_format)
	raw: partial = partial(_raw_format)

	def __call__(self: Any, solution: Solution) -> str:
		"""Converts the enumeration member into the corresponding function call.

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
