# Copyright 2013 The Debian Package Tracking System Developers
# See the COPYRIGHT file at the top-level directory of this distribution and
# at http://deb.li/ptsauthors
#
# This file is part of the Package Tracking System. It is subject to the
# license terms in the LICENSE file found in the top-level directory of
# this distribution and at http://deb.li/ptslicense. No part of the Package
# Tracking System, including this file, may be copied, modified, propagated, or
# distributed except according to the terms contained in the LICENSE file.

from __future__ import unicode_literals
from pts.core.utils.plugins import PluginRegistry
from pts.core.utils.datastructures import DAG
from django.utils import six

from collections import defaultdict


class BaseTask(six.with_metaclass(PluginRegistry)):
    """
    A class representing the base class for all data processing tasks of the
    PTS.

    The subclasses of this class are automatically registered when created.
    """
    DEPENDS_ON_EVENTS = ()
    PRODUCES_EVENTS = ()

    @classmethod
    def task_name(cls):
        if hasattr(cls, 'NAME'):
            return cls.NAME
        else:
            return cls.__name__

    def __init__(self):
        #: A flag signalling whether the task has received any events.
        #: A task with no received events does not need to run.
        self.event_received = False
        self._raised_events = []

    def execute(self):
        """
        Performs the actual processing of the task.

        This method must raise appropriate events by using the `raise_event`
        method during the processing so that tasks which are dependent on those
        events can be notified.
        """
        pass

    @property
    def raised_events(self):
        """
        Return an iterable of Events which the task raised during its execution
        """
        return self._raised_events

    def raise_event(self, event_name, arguments=None):
        """
        Helper method which should be used by subclasses to signal that an
        event has been triggered. The object given in the arguments parameter
        will be passed on to to the `Event` instance's arguments and become
        available to any tasks which receive this event.
        """
        self._raised_events.append(Event(event_name, arguments))

    def receive_event(self, event):
        """
        This method is used by clients to notify the task that a specific event
        has been triggered while processing another task.

        If the task depends on this event, the `event_received` flag is set and
        additional, subclass specific, processing is initiated (by calling the
        `process_event` method).
        """
        if event.name in self.DEPENDS_ON_EVENTS:
            # In the general case, an event can come with some arguments, but
            # BaseTask subclasses need to implement this specifically.
            self.process_event(event)
            self.event_received = True

    def process_event(self, event):
        """
        Helper method which should be implemented by subclasses which require
        specific processing of received events.
        """
        pass


class Event(object):
    """
    A class representing a particular event raised by a task.
    """
    def __init__(self, name, arguments=None):
        self.name = name
        self.arguments = arguments


class Job(object):
    """
    A class used to initialize and run a set of interdependent tasks.
    """
    def __init__(self, initial_task):
        """
        Instantiates a new Job instance based on the given initial_task.

        The task contains a DAG instance which is constructed by using all
        possible dependencies between tasks. While running the tasks, the
        job keeps track of emitted events and makes sure that a task with
        no received events is not run, even though we used those dependencies
        when constructing the DAG.

        This way, we are guaranteed that tasks execute in the correct order and
        at most once -- after all the tasks which could possibly raise an event
        which that task depends on.
        """
        # Build this job's DAG based on the full DAG of all tasks.
        self.job_dag = build_full_task_dag()
        # The full DAG contains dependencies between Task classes, but the job
        # needs to have Task instances, so it instantiates the Tasks dependent
        # on the initial task.
        reachable_tasks = self.job_dag.nodes_reachable_from(initial_task)
        for task_class in self.job_dag.all_nodes:
            if task_class is initial_task or task_class in reachable_tasks:
                task = task_class()
                if task_class is initial_task:
                    # The initial task gets flagged with an event so that we
                    # make sure that it is not skipped.
                    task.event_received = True
                self.job_dag.replace_node(task_class, task)
            else:
                # Remove tasks which are not reachable from the initial task
                # from the job Tasks DAG, since those are in no way dependent
                # on it and will not need to run.
                self.job_dag.remove_node(task_class)

    def _update_task_events(self, processed_task):
        """
        Updates the received events of all tasks which depend on events the
        processed_task has raised.
        """
        for dependent_task in self.job_dag.dependent_nodes(processed_task):
            # Update this task's raised events.
            for event in processed_task.raised_events:
                dependent_task.receive_event(event)

    def run(self):
        """
        Starts the Job processing.

        It runs all tasks which depend on the given initial task, but only if
        the required events are emitted and received.
        """
        for task in self.job_dag.topsort_nodes():
            # A task does not need to run if none of the events it depends on
            # have been raised by this point.
            # If it's that task's turn in topological sort order when all
            # dependencies are used to construct the graph, it is guaranteed
            # that none of its dependencies will ever be raised since the tasks
            # which come afterwards do not raise any events which this task
            # depends on.
            # (Otherwise that task would have to be ahead of this one in the
            #  topological sort order.)
            if task.event_received:
                # Run task
                task.execute()
                # Update dependent tasks based on events raised
                self._update_task_events(task)


def build_task_event_dependency_graph():
    """
    Returns a dict mapping event names to a two-tuple of a list of task classes
    which produce the event and a list of task classes which depend on the
    event, respectively.
    """
    events = defaultdict(lambda: ([], []))
    for task in BaseTask.plugins:
        if task is BaseTask:
            continue
        for event in task.PRODUCES_EVENTS:
            events[event][0].append(task)
        for event in task.DEPENDS_ON_EVENTS:
            events[event][1].append(task)

    return events


def build_full_task_dag():
    """
    Returns a DAG instance representing the dependencies between Task classes
    based on the events they produce and depend on.
    """
    dag = DAG()
    # Add all existing tasks to the dag.
    for task in BaseTask.plugins:
        if task is not BaseTask:
            dag.add_node(task)

    # Create the edges of the graph by creating an edge between each pair of
    # tasks T1, T2 where T1 produces an event E and T2 depends on the event E.
    from itertools import product as cross_product
    events = build_task_event_dependency_graph()
    for event_producers, event_consumers in events.values():
        for node1, node2 in cross_product(event_producers, event_consumers):
            dag.add_edge(node1, node2)

    return dag


def run_task(initial_task):
    """
    Receives a class of the task which should be executed and makes sure that
    all the tasks which have data dependencies on this task are ran after it.

    This is a convenience function which delegates this to a Job class instance
    """
    job = Job(initial_task)
    return job.run()