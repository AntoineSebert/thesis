#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import Callable, Iterable
from model import Task

# take offset into account ?
sort: Callable[[Iterable[Task]], Iterable[Task]] = lambda tasks: sorted(tasks, key=lambda task: task.deadline)
