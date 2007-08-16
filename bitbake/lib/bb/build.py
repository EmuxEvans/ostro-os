# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
#
# BitBake 'Build' implementation
#
# Core code for function execution and task handling in the
# BitBake build tools.
#
# Copyright (C) 2003, 2004  Chris Larson
#
# Based on Gentoo's portage.py.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
#Based on functions from the base bb module, Copyright 2003 Holger Schurig

from bb import data, event, mkdirhier, utils
import bb, os, sys

# events
class FuncFailed(Exception):
    """
    Executed function failed
    First parameter a message
    Second paramter is a logfile (optional)
    """

class EventException(Exception):
    """Exception which is associated with an Event."""

    def __init__(self, msg, event):
        self.args = msg, event

class TaskBase(event.Event):
    """Base class for task events"""

    def __init__(self, t, d ):
        self._task = t
        event.Event.__init__(self, d)

    def getTask(self):
        return self._task

    def setTask(self, task):
        self._task = task

    task = property(getTask, setTask, None, "task property")

class TaskStarted(TaskBase):
    """Task execution started"""

class TaskSucceeded(TaskBase):
    """Task execution completed"""

class TaskFailed(TaskBase):
    """Task execution failed"""
    def __init__(self, msg, logfile, t, d ):
        self.logfile = logfile
        self.msg = msg
        TaskBase.__init__(self, t, d)

class InvalidTask(TaskBase):
    """Invalid Task"""

# functions

def exec_func(func, d, dirs = None):
    """Execute an BB 'function'"""

    body = data.getVar(func, d)
    if not body:
        return

    ispython = data.getVarFlag(func, "python", d)

    if not dirs:
        dirs = (data.getVarFlag(func, 'dirs', d) or "").split()
    for adir in dirs:
        adir = data.expand(adir, d)
        mkdirhier(adir)

    if len(dirs) > 0:
        adir = dirs[-1]
    else:
        adir = data.getVar('B', d, 1)

    adir = data.expand(adir, d)

    # Save current directory
    try:
        prevdir = os.getcwd()
    except OSError:
        prevdir = data.expand('${TOPDIR}', d)

    # Setup logfiles
    t = data.getVar('T', d, 1)
    if not t:
        bb.msg.fatal(bb.msg.domain.Build, "T not set")
    mkdirhier(t)
    logfile = "%s/log.%s.%s" % (t, func, str(os.getpid()))
    runfile = "%s/run.%s.%s" % (t, func, str(os.getpid()))

    # Change to correct directory (if specified)
    if adir and os.access(adir, os.F_OK):
        os.chdir(adir)

    # Handle logfiles
    si = file('/dev/null', 'r')
    try:
        if bb.msg.debug_level['default'] > 0 or ispython:
            so = os.popen("tee \"%s\"" % logfile, "w")
        else:
            so = file(logfile, 'w')
    except OSError, e:
        bb.msg.error(bb.msg.domain.Build, "opening log file: %s" % e)
        pass

    se = so

    # Dup the existing fds so we dont lose them
    osi = [os.dup(sys.stdin.fileno()), sys.stdin.fileno()]
    oso = [os.dup(sys.stdout.fileno()), sys.stdout.fileno()]
    ose = [os.dup(sys.stderr.fileno()), sys.stderr.fileno()]

    # Replace those fds with our own
    os.dup2(si.fileno(), osi[1])
    os.dup2(so.fileno(), oso[1])
    os.dup2(se.fileno(), ose[1])

    try:
        # Run the function
        if ispython:
            exec_func_python(func, d, runfile, logfile)
        else:
            exec_func_shell(func, d, runfile, logfile)

        # Restore original directory
        try:
            os.chdir(prevdir)
        except:
            pass

    finally:
        # Restore the backup fds
        os.dup2(osi[0], osi[1])
        os.dup2(oso[0], oso[1])
        os.dup2(ose[0], ose[1])

        # Close our logs
        si.close()
        so.close()
        se.close()

        # Close the backup fds
        os.close(osi[0])
        os.close(oso[0])
        os.close(ose[0])

def exec_func_python(func, d, runfile, logfile):
    """Execute a python BB 'function'"""
    import re, os

    tmp  = "def " + func + "():\n%s" % data.getVar(func, d)
    tmp += '\n' + func + '()'

    f = open(runfile, "w")
    f.write(tmp)
    comp = utils.better_compile(tmp, func, bb.data.getVar('FILE', d, 1) )
    g = {} # globals
    g['bb'] = bb
    g['os'] = os
    g['d'] = d
    utils.better_exec(comp, g, tmp, bb.data.getVar('FILE',d,1))


def exec_func_shell(func, d, runfile, logfile):
    """Execute a shell BB 'function' Returns true if execution was successful.

    For this, it creates a bash shell script in the tmp dectory, writes the local
    data into it and finally executes. The output of the shell will end in a log file and stdout.

    Note on directory behavior.  The 'dirs' varflag should contain a list
    of the directories you need created prior to execution.  The last
    item in the list is where we will chdir/cd to.
    """

    deps = data.getVarFlag(func, 'deps', d)
    check = data.getVarFlag(func, 'check', d)
    if check in globals():
        if globals()[check](func, deps):
            return

    f = open(runfile, "w")
    f.write("#!/bin/sh -e\n")
    if bb.msg.debug_level['default'] > 0: f.write("set -x\n")
    data.emit_env(f, d)

    f.write("cd %s\n" % os.getcwd())
    if func: f.write("%s\n" % func)
    f.close()
    os.chmod(runfile, 0775)
    if not func:
        bb.msg.error(bb.msg.domain.Build, "Function not specified")
        raise FuncFailed("Function not specified for exec_func_shell")

    # execute function
    if data.getVarFlag(func, "fakeroot", d):
        maybe_fakeroot = "PATH=\"%s\" fakeroot " % bb.data.getVar("PATH", d, 1)
    else:
        maybe_fakeroot = ''
    lang_environment = "LC_ALL=C "
    ret = os.system('%s%ssh -e %s' % (lang_environment, maybe_fakeroot, runfile))

    if ret == 0:
        return

    bb.msg.error(bb.msg.domain.Build, "Function %s failed" % func)
    raise FuncFailed("function %s failed" % func, logfile)


def exec_task(task, d):
    """Execute an BB 'task'

       The primary difference between executing a task versus executing
       a function is that a task exists in the task digraph, and therefore
       has dependencies amongst other tasks."""

    # check if the task is in the graph..
    task_graph = data.getVar('_task_graph', d)
    if not task_graph:
        task_graph = bb.digraph()
        data.setVar('_task_graph', task_graph, d)
    task_cache = data.getVar('_task_cache', d)
    if not task_cache:
        task_cache = []
        data.setVar('_task_cache', task_cache, d)
    if not task_graph.hasnode(task):
        raise EventException("Missing node in task graph", InvalidTask(task, d))

    # check whether this task needs executing..
    if stamp_is_current(task, d):
        return 1

    # follow digraph path up, then execute our way back down
    def execute(graph, item):
        if data.getVarFlag(item, 'task', d):
            if item in task_cache:
                return 1

            if task != item:
                # deeper than toplevel, exec w/ deps
                exec_task(item, d)
                return 1

            try:
                bb.msg.debug(1, bb.msg.domain.Build, "Executing task %s" % item)
                old_overrides = data.getVar('OVERRIDES', d, 0)
                localdata = data.createCopy(d)
                data.setVar('OVERRIDES', 'task_%s:%s' % (item, old_overrides), localdata)
                data.update_data(localdata)
                event.fire(TaskStarted(item, localdata))
                exec_func(item, localdata)
                event.fire(TaskSucceeded(item, localdata))
                task_cache.append(item)
                data.setVar('_task_cache', task_cache, d)
            except FuncFailed, message:
                # Try to extract the optional logfile
                try:
                    (msg, logfile) = message
                except:
                    logfile = None
                    msg = message
                bb.msg.note(1, bb.msg.domain.Build, "Task failed: %s" % message )
                failedevent = TaskFailed(msg, logfile, item, d)
                event.fire(failedevent)
                raise EventException("Function failed in task: %s" % message, failedevent)

    if data.getVarFlag(task, 'dontrundeps', d):
        execute(None, task)
    else:
        task_graph.walkdown(task, execute)

    # make stamp, or cause event and raise exception
    if not data.getVarFlag(task, 'nostamp', d):
        make_stamp(task, d)

def extract_stamp_data(d, fn):
    """
    Extracts stamp data from d which is either a data dictonary (fn unset) 
    or a dataCache entry (fn set). 
    """
    if fn:
        return (d.task_queues[fn], d.stamp[fn], d.task_deps[fn])
    task_graph = data.getVar('_task_graph', d)
    if not task_graph:
        task_graph = bb.digraph()
        data.setVar('_task_graph', task_graph, d)
    return (task_graph, data.getVar('STAMP', d, 1), None)

def extract_stamp(d, fn):
    """
    Extracts stamp format which is either a data dictonary (fn unset) 
    or a dataCache entry (fn set). 
    """
    if fn:
        return d.stamp[fn]
    return data.getVar('STAMP', d, 1)

def stamp_is_current(task, d, file_name = None, checkdeps = 1):
    """
    Check status of a given task's stamp. 
    Returns 0 if it is not current and needs updating.
    (d can be a data dict or dataCache)
    """

    (task_graph, stampfn, taskdep) = extract_stamp_data(d, file_name)

    if not stampfn:
        return 0

    stampfile = "%s.%s" % (stampfn, task)
    if not os.access(stampfile, os.F_OK):
        return 0

    if checkdeps == 0:
        return 1

    import stat
    tasktime = os.stat(stampfile)[stat.ST_MTIME]

    _deps = []
    def checkStamp(graph, task):
        # check for existance
        if file_name:
            if 'nostamp' in taskdep and task in taskdep['nostamp']:
                return 1
        else:
            if data.getVarFlag(task, 'nostamp', d):
                return 1

        if not stamp_is_current(task, d, file_name, 0						):
            return 0

        depfile = "%s.%s" % (stampfn, task)
        deptime = os.stat(depfile)[stat.ST_MTIME]
        if deptime > tasktime:
            return 0
        return 1

    return task_graph.walkdown(task, checkStamp)

def stamp_internal(task, d, file_name):
    """
    Internal stamp helper function
    Removes any stamp for the given task
    Makes sure the stamp directory exists
    Returns the stamp path+filename
    """
    stamp = extract_stamp(d, file_name)
    if not stamp:
        return
    stamp = "%s.%s" % (stamp, task)
    mkdirhier(os.path.dirname(stamp))
    # Remove the file and recreate to force timestamp
    # change on broken NFS filesystems
    if os.access(stamp, os.F_OK):
        os.remove(stamp)
    return stamp

def make_stamp(task, d, file_name = None):
    """
    Creates/updates a stamp for a given task
    (d can be a data dict or dataCache)
    """
    stamp = stamp_internal(task, d, file_name)
    if stamp:
        f = open(stamp, "w")
        f.close()

def del_stamp(task, d, file_name = None):
    """
    Removes a stamp for a given task
    (d can be a data dict or dataCache)
    """
    stamp_internal(task, d, file_name)

def add_task(task, deps, d):
    task_graph = data.getVar('_task_graph', d)
    if not task_graph:
        task_graph = bb.digraph()

    task = data.expand(task, d)

    data.setVarFlag(task, 'task', 1, d)
    task_graph.addnode(task, None)
    for dep in deps:
        dep = data.expand(dep, d)
        if not task_graph.hasnode(dep):
            task_graph.addnode(dep, None)
        task_graph.addnode(task, dep)
    # don't assume holding a reference
    data.setVar('_task_graph', task_graph, d)

    task_deps = data.getVar('_task_deps', d)
    if not task_deps:
        task_deps = {}
    def getTask(name):
        deptask = data.getVarFlag(task, name, d)
        if deptask:
            deptask = data.expand(deptask, d)
            if not name in task_deps:
                task_deps[name] = {}
            task_deps[name][task] = deptask
    getTask('deptask')
    getTask('rdeptask')
    getTask('recrdeptask')
    getTask('nostamp')

    data.setVar('_task_deps', task_deps, d)

def remove_task(task, kill, d):
    """Remove an BB 'task'.

       If kill is 1, also remove tasks that depend on this task."""

    task_graph = data.getVar('_task_graph', d)
    if not task_graph:
        task_graph = bb.digraph()
    if not task_graph.hasnode(task):
        return

    data.delVarFlag(task, 'task', d)
    ref = 1
    if kill == 1:
        ref = 2
    task_graph.delnode(task, ref)
    data.setVar('_task_graph', task_graph, d)

def task_exists(task, d):
    task_graph = data.getVar('_task_graph', d)
    if not task_graph:
        task_graph = bb.digraph()
        data.setVar('_task_graph', task_graph, d)
    return task_graph.hasnode(task)
