"""class for handling .oe files

   Reads the file and obtains its metadata"""

import re, oe, string, os, sys
import oe
import oe.fetch
from oe import debug, data, fetch, fatal

from oe.parse.ConfHandler import include, init

__func_start_regexp__    = re.compile( r"((?P<py>python)\s*)*(?P<func>\w+)\s*\(\s*\)\s*{$" )
__inherit_regexp__       = re.compile( r"inherit\s+(.+)" )
__export_func_regexp__   = re.compile( r"EXPORT_FUNCTIONS\s+(.+)" )
__addtask_regexp__       = re.compile("addtask\s+(?P<func>\w+)\s*((before\s*(?P<before>((.*(?=after))|(.*))))|(after\s*(?P<after>((.*(?=before))|(.*)))))*")
__addhandler_regexp__       = re.compile( r"addhandler\s+(.+)" )

__infunc__ = ""
__body__   = []
__oepath_found__ = 0
__classname__ = ""
classes = [ None, ]

def supports(fn):
	return fn[-3:] == ".oe" or fn[-8:] == ".oeclass"

__inherit_cache = []
def inherit(files, d):
	fn = ""
	lineno = 0
	for f in files:
		file = data.expand(f, d)
		if file[0] != "/" and file[-8:] != ".oeclass":
			file = "classes/%s.oeclass" % file

		if not file in __inherit_cache:
			debug(2, "%s:%d: inheriting %s" % (fn, lineno, file))
			__inherit_cache.append(file)
			include(fn, file, d)


def handle(fn, d = {}):
	global __func_start_regexp__, __inherit_regexp__, __export_func_regexp__, __addtask_regexp__, __addhandler_regexp__, __infunc__, __body__, __oepath_found__
	__body__ = []
	__oepath_found__ = 0
	__infunc__ = ""
	__classname__ = ""

	(root, ext) = os.path.splitext(os.path.basename(fn))
	if ext == ".oeclass":
		__classname__ = root
		classes.append(__classname__)

	init(d)
	data.inheritFromOS(2, d)
	oepath = ['.']
	if not os.path.isabs(fn):
		f = None
		voepath = data.getVar("OEPATH", d)
		if voepath:
			oepath += voepath.split(":")
		for p in oepath:
			p = data.expand(p, d)
			if os.access(os.path.join(p, fn), os.R_OK):
				f = open(os.path.join(p, fn), 'r')
		if f is None:
			raise IOError("file not found")
	else:
		f = open(fn,'r')

	inheritclasses = data.getVar("INHERIT", d)
	if inheritclasses:
		i = inheritclasses.split()
	else:
		i = []
	if not "base" in i and __classname__ != "base":
		i[0:0] = ["base"]
	inherit(i, d)

	lineno = 0
	while 1:
		lineno = lineno + 1
		s = f.readline()
		if not s: break
		w = s.strip()
		if not w: continue		# skip empty lines
		s = s.rstrip()
		if s[0] == '#': continue	# skip comments
		while s[-1] == '\\':
			s2 = f.readline()[:-1].strip()
			s = s[:-1] + s2
		feeder(lineno, s, fn, d)
	if ext == ".oeclass":
		classes.remove(__classname__)
	else:
		set_automatic_vars(fn, d)
		set_additional_vars(fn, d)
	return d

def feeder(lineno, s, fn, d):
	global __func_start_regexp__, __inherit_regexp__, __export_func_regexp__, __addtask_regexp__, __addhandler_regexp__, __infunc__, __body__, __oepath_found__, classes, oe
	if __infunc__:
		if s == '}':
			__body__.append('')
			data.setVar(__infunc__, string.join(__body__, '\n'), d)
			data.setVarFlag(__infunc__, "func", 1, d)
			__infunc__ = ""
			__body__ = []
		else:
			__body__.append(s)
		return
			
	m = __func_start_regexp__.match(s)
	if m:
		__infunc__ = m.group("func")
		key = __infunc__
		if m.group("py") is not None:
			data.setVarFlag(key, "python", "1", d)
		return

	__word__ = re.compile(r"\S+")

	m = __export_func_regexp__.match(s)
	if m:
		fns = m.group(1)
		n = __word__.findall(fns)
		for f in n:
			allvars = []
			allvars.append(f)
			allvars.append("%s_%s" % (classes[-1], f))

			vars = [[ allvars[0], allvars[1] ]]
			if len(classes) > 1 and classes[-2] is not None:
				allvars.append("%s_%s" % (classes[-2], f))
				vars = []
				vars.append([allvars[2], allvars[1]])
				vars.append([allvars[0], allvars[2]])

			for (var, calledvar) in vars:
				for flag in [ "func", "python", "dirs" ]:
					__dirty = 0
					if data.getVarFlag(var, flag, d):
						__dirty = var
					if data.getVarFlag(calledvar, flag, d):
						__dirty = calledvar
					if __dirty:
						for v in allvars:
							data.setVarFlag(v, flag, data.getVarFlag(__dirty, flag, d), d)
				if data.getVarFlag(calledvar, "python", d):
					data.setVar(var, """
	return exec_func('%s', d)
""" % calledvar, d)
				else:
					data.setVar(var, "\t%s\n" % calledvar, d)

		return

	m = __addtask_regexp__.match(s)
	if m:
		func = m.group("func")
		before = m.group("before")
		after = m.group("after")
		if func is None:
			return
		var = "do_" + func

		data.setVarFlag(var, "task", 1, d)

		if after is not None:
			# set up deps for function
			data.setVarFlag(var, "deps", after.split(), d)
		if before is not None:
			# set up things that depend on this func 
			data.setVarFlag(var, "postdeps", before.split(), d)
		return

	m = __addhandler_regexp__.match(s)
	if m:
		fns = m.group(1)
		hs = __word__.findall(fns)
		for h in hs:
			data.setVarFlag(h, "handler", 1, d)
		return

	m = __inherit_regexp__.match(s)
	if m:

		files = m.group(1)
		n = __word__.findall(files)
		inherit(n, d)
		return

	from oe.parse import ConfHandler
	return ConfHandler.feeder(lineno, s, fn, d)

def set_automatic_vars(file, d):
	"""Deduce per-package environment variables"""

	debug(2, "setting automatic vars")
	pkg = oe.catpkgsplit(file)
	if pkg == None:
		fatal("package file not in valid format")

	data.setVar('CATEGORY', pkg[0], d)
	data.setVar('PN', pkg[1], d)
	data.setVar('PV', pkg[2], d)
	data.setVar('PR', pkg[3], d)
	data.setVar('P', '${PN}-${PV}', d)
	data.setVar('PF', '${P}-${PR}', d)

	for s in ['${TOPDIR}/${CATEGORY}/${PF}', 
		  '${TOPDIR}/${CATEGORY}/${PN}-${PV}',
		  '${TOPDIR}/${CATEGORY}/files',
		  '${TOPDIR}/${CATEGORY}']:
		s = data.expand(s, d)
		if os.access(s, os.R_OK):
			data.setVar('FILESDIR', s, d)
			break

	data.setVar('WORKDIR', '${TMPDIR}/${CATEGORY}/${PF}', d)
	data.setVar('T', '${WORKDIR}/temp', d)
	data.setVar('D', '${WORKDIR}/image', d)
	if not data.getVar('S', d):
		data.setVar('S', '${WORKDIR}/${P}', d)
	data.setVar('SLOT', '0', d)
	data.inheritFromOS(3, d)

def set_additional_vars(file, d):
	"""Deduce rest of variables, e.g. ${A} out of ${SRC_URI}"""

	debug(2,"set_additional_vars")

	data.inheritFromOS(4, d)
	src_uri = data.getVar('SRC_URI', d)
	if not src_uri:
		return
	src_uri = data.expand(src_uri, d)

	# Do we already have something in A?
	a = data.getVar('A', d)
	if a:
		a = data.expand(a, d).split()
	else:
		a = []

	from oe import fetch
	try:
		fetch.init(src_uri.split())
	except fetch.NoMethodError:
		pass

	a += fetch.localpaths()
	del fetch
	data.setVar('A', string.join(a), d)


# Add us to the handlers list
from oe.parse import handlers
handlers.append({'supports': supports, 'handle': handle, 'init': init})
del handlers
