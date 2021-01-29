#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# IMPORTS #############################################################################################################

from __future__ import annotations

from collections.abc import Iterator, Reversible, Set
from dataclasses import dataclass, field
from functools import total_ordering
from math import fsum

from graph_model import App, Job, Task

from sortedcontainers import SortedSet  # type: ignore


# CLASSES AND TYPE ALIASES ############################################################################################

@dataclass
@total_ordering
class Core(Set, Reversible):
	"""Represents a core.

	Attributes
	----------
	id : int
		The core id within a `Processor`.
	processor : Processor
		The processor this core belongs to.
	tasks : SortedSet[Task]
		The tasks attached to this core, sorted by criticality.
	"""

	id: int
	processor: Processor
	tasks: list[Task] = field(compare=False, default_factory=list) #pqueue

	def workload(self: Core) -> float:
		"""The workload of the core.

		Parameters
		----------
		self : Core
			The instance of `Core`.

		Returns
		-------
		float
			The workload sum of all tasks on this core.
		"""

		return fsum(task.workload for task in self) if self.tasks else 0.0

	def short(self: Core) -> str:
		"""A short description of a core.

		Parameters
		----------
		self : Core
			The instance of `Core`.

		Returns
		-------
		str
			The short description.
		"""

		return f"{self.processor.id} / {self.id} : {self.workload()}"

	def pformat(self: Core, level: int = 0) -> str:
		"""A complete description of a core.

		Parameters
		----------
		self : Core
			The instance of `Core`.
		level : int, optional
			The indentation level (default: 0).

		Returns
		-------
		str
			The complete description.
		"""

		return ("\n" + ("\t" * level) + f"core {{ id : {self.id}; processor : {self.processor.id}; workload: {self.workload}; }}")

	# HASHABLE

	def __hash__(self: Core) -> int:
		return hash(str(self.id) + str(self.processor.id))

	# TOTAL ORDERING

	def __lt__(self: Core, other: object) -> bool:
		if isinstance(other, Core):
			return self.workload() < other.workload()
		else:
			return NotImplemented

	# SET

	def __contains__(self: Core, item: object) -> bool:
		if isinstance(item, Task):
			return self.tasks.__contains__(item)
		else:
			return NotImplemented

	def __len__(self: Core) -> int:
		return self.tasks.__len__()

	# ITERABLE

	def __iter__(self: Core) -> Iterator[Task]:
		return self.tasks.__iter__()

	# REVERSIBLE

	def __reversed__(self: Core) -> Iterator[Task]:
		return self.tasks.__reversed__()

	# DEEPCOPY

	def __deepcopy__(self: Core, memo: dict[int, object]) -> Processor:
		cls = self.__class__
		result = cls.__new__(cls)
		memo[id(self)] = result

		result.id = self.id
		result.processor = self.processor
		result.tasks = self.tasks

		return result


@dataclass
@total_ordering
class Processor(Set, Reversible):
	"""Represents a processor.

	Attributes
	----------
	id : int
		The processor within an `Architecture`.
	cores : SortedSet[Core]
		The set containing the `Core` objects within the Processor.
	apps : SortedSet[App]
		Applications to be scheduled on the Processor.
	"""

	id: int
	cores: SortedSet[Core] = field(compare=False, default_factory=SortedSet)
	apps: SortedSet[App] = field(compare=False, default_factory=SortedSet)

	def workload(self: Processor) -> float:
		"""The workload of the processor.

		Parameters
		----------
		self : Processor
			The instance of `Processor`.

		Returns
		-------
		float
			The sum of workload of all cores on this processor.
		"""

		return fsum(core.workload() for core in self) if self.cores else 0.0

	def min_core(self: Processor) -> Core:
		"""The core on the processor with the lowest workload.

		Parameters
		----------
		self : Processor
			The instance of `Processor`.

		Returns
		-------
		int
			The core with the minimal workload.
		"""

		return min(self)

	def pformat(self: Processor, level: int = 0) -> str:
		"""A complete description of a processor.

		Parameters
		----------
		self : Processor
			The instance of `Processor`.
		level : int, optional
			The indentation level (default: 0).

		Returns
		-------
		str
			The complete description.
		"""

		i = "\n" + ("\t" * level)

		return f"{i}cpu {{{i}\tid : {self.id};" + "".join(core.pformat(level + 1) for core in self) + i + "}"

	# HASHABLE

	def __hash__(self: Processor) -> int:
		return hash(str(self.id))

	# TOTAL ORDERING

	def __lt__(self: Processor, other: object) -> bool:
		if isinstance(other, Processor):
			return self.workload() < other.workload()
		else:
			return NotImplemented

	# SET

	def __contains__(self: Processor, item: object) -> bool:
		if isinstance(item, Core):
			return self.cores.__contains__(item)
		else:
			return NotImplemented

	def __len__(self: Processor) -> int:
		return self.cores.__len__()

	# ITERABLE

	def __iter__(self: Processor) -> Iterator[Core]:
		return self.cores.__iter__()

	# REVERSIBLE

	def __reversed__(self: Processor) -> Iterator[Core]:
		return self.cores.__reversed__()


"""An set of `Processor` representing an `Architecture`."""
Architecture = set[Processor]

"""Maps a core to a set of tasks."""
CoreTaskMap = dict[Core, list[Task]]

"""Maps a core to a set of jobs."""
CoreJobMap = dict[Core, list[Job]]
