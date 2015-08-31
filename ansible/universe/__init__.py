# copyright (c) 2015 fclaerhout.fr, released under the MIT license.
# coding: utf-8

"""
Ansible role build tool.

Usage:
  ansible-universe [options] TARGET...
  ansible-universe --help

Options:
  -C PATH, --directory PATH  set working directory
  -r URL, --repository URL   set HTTP repository
  -x PATHS, --exclude PATHS  comma-separated list of paths to ignore
  -v, --verbose              output executed commands
  -h, --help                 display full help text
  --no-color                 disable colored output
  -a, --all                  with clean, remove distdir

Where TARGET is in:
  * init        instantiate role template
  * dist        generate ansible distributable role files
  * check       include role in a dummy playbook and check syntax
  * package     package role
  * publish -r  publish role to a HTTP repository
  * distclean   delete generated files

Example:
  $ mkdir foo
  $ ansible-universe -C foo init dist check

Build manifest:
  Universe uses the galaxy manifest, meta/main.yml
  with the following additional attributes:
  * version
  * variables, maps names to descriptions
  * inconditions, maps tasks filename to include conditions
"""

import textwrap, glob, time, sys, os

import docopt, jinja2, utils, yaml # 3rd-party

DEFAULTS_PATH = os.path.join("defaults", "main.yml")
README_PATH = "README.md"
META_PATH = os.path.join("meta", "main.yml")
TASKSDIR = "tasks"
MAINTASK_PATH = os.path.join(TASKSDIR, "main.yml")
DISTDIR = "dist"

class Error(utils.Error): pass

def unmarshall(path, default = None):
	"custom unmarshaller with yaml support"
	def _unmarshall_yaml(path):
		with open(path, "r") as fp:
			return yaml.load(fp)
	return utils.unmarshall(
		path = path,
		default = default,
		helpers = {
			".yml": _unmarshall_yaml,
		})

def marshall(obj, path, extname = None):
	"custom marshaller with yaml support"
	def _marshall_yaml(obj, fp):
		yaml.dump(obj, fp, explicit_start = True, default_flow_style = False)
	utils.trace("writing", path)
	utils.marshall(
		obj = obj,
		path = path,
		extname = extname,
		helpers = {
			".yml": _marshall_yaml,
		},
		overwrite = True)

class Role(object):

	def __init__(self, excluded_paths = None):
		self.excluded_paths = excluded_paths or () # user files not to be overwritten

	@property
	def name(self):
		"return role name"
		return os.path.basename(os.getcwd())

	def _get_manifest(self):
		"return role manifest as a dict"
		return unmarshall(META_PATH)

	def _set_manifest(self, _dict):
		marshall(
			obj = _dict,
			path = META_PATH)

	manifest = property(_get_manifest, _set_manifest)

	def _get_version(self):
		"return role version"
		return self.manifest["version"]

	def _set_version(self, _str):
		_dict = self.manifest
		_dict["version"] = _str
		self.manifest = _dict

	version = property(_get_version, _set_version)

	@property
	def author(self):
		"return role author"
		return self.manifest["galaxy_info"]["author"]

	@property
	def platforms(self):
		"return the list of supported platforms {'name':..., 'versions':...}"
		return self.manifest["galaxy_info"].get("platforms", ())

	@property
	def variables(self):
		"return dict mapping variable names to {'default':..., 'description':...}"
		_dict = {}
		for key, value in (unmarshall(DEFAULTS_PATH) or {}).items():
			if not key in _dict:
				_dict[key] = {"default": value}
			else:
				_dict[key]["default"] = value
		for key, value in self.manifest.get("variables", {}).items():
			if not key in _dict:
				_dict[key] = {"description": value}
			else:
				_dict[key]["description"] = value
		return _dict

	@property
	def description(self):
		"return role description"
		return self.manifest["galaxy_info"]["description"]

	@property
	def dependencies(self):
		"return list of role dependencies"
		return self.manifest["dependencies"]

	@property
	def inconditions(self):
		"return dict mapping tasks/ playbooks to include conditions"
		return self.manifest.get("inconditions", {})

	def init(self):
		"use ansible-galaxy to populate current directory"
		utils.check_call("ansible-galaxy", "init", self.name, "--force")
		for path in (README_PATH, MAINTASK_PATH):
			utils.remove(os.path.join(self.name, path))
		for basename in os.listdir(self.name):
			os.rename(os.path.join(self.name, basename), basename)
		utils.remove(self.name)
		self.version = "0.0.1"

	def _generate_readme(self):
		template = """
			<!-- THIS IS A GENERATED FILE, DO NOT EDIT -->

			# {{ name }}

			{{ description or "No description (yet.)" }}

			* * *

			## Supported Platforms

			{% for ptf in platforms %}
			  * {{ ptf.name }}
			{% else %}
			No supported platform specified (yet.)
			{% endfor %}

			## Variables

			| Name | Default | Description |
			|------|---------|-------------|
			{% for var in variables %}| {{ var.name }} | {{ var.default }} | {{ var.description }} |
			{% endfor %}

			## Usage

			Read Ansible documentation at https://docs.ansible.com/playbooks_roles.html#roles.

			## Maintenance

			Install [ansible-utils](https://github.com/fclaerho/ansible-utils)
			and run `ansible-role dist` to re-generate this distribution.

			The following files are generated or updated based on the role manifest `meta/main.yml`:
			  * defaults/main.yml
			  * tasks/main.yml
			  * README.md
		"""
		text = jinja2.Template(textwrap.dedent(template)).render(**{
			"description": self.description,
			"platforms": self.platforms,
			"variables": self.variables,
			"name": self.name,
		})
		marshall(
			obj = text,
			path = README_PATH,
			extname = ".txt")

	def _generate_maintask(self):
		platforms = self.platforms
		mainplays = []
		if platforms:
			mainplays.append({
				"name": "assert the target platform is supported",
				"fail": {
					"msg": "unsupported platform -- please contact the role maintainer for support",
				},
				"when": "ansible_distribution not in %s" % list(platform["name"] for platform in platforms),
			})
		for name in glob.glob(os.path.join(TASKSDIR, "*.yml")):
			if name in self.inconditions:
				mainplays.append({
					"include": name,
					"when": self.inconditions[name],
				})
			else:
				mainplays.append({
					"include": name,
				})
		marshall(
			obj = mainplays,
			path = MAINTASK_PATH)

	def dist(self):
		for path, generate in {
			README_PATH: self._generate_readme,
			MAINTASK_PATH: self._generate_maintask,
		}.items():
			if not path in self.excluded_paths:
				generate()
			else:
				utils.trace(path, "in excluded path, ignored")

	def check_syntax(self):
		"generate a playbook using the role and syntax-check it"
		tmpdir = utils.mkdir()
		playbook = [{
			"hosts": "127.0.0.1",
			"connection": "local",
			"roles": [self.name],
		}]
		marshall(
			obj = playbook,
			path = os.path.join(tmpdir, "playbook.yml"))
		inventory = "localhost ansible_connection=local"
		marshall(
			obj = inventory,
			path = os.path.join(tmpdir, "inventory.cfg"),
			extname = ".txt")
		cwd = os.getcwd()
		config = {
			"defaults": {
				"roles_path": os.path.dirname(cwd),
				"hostfile": "inventory.cfg",
			}
		}
		marshall(
			obj = config,
			path = os.path.join(tmpdir, "ansible.cfg"))
		utils.chdir(tmpdir)
		utils.check_call("ansible-playbook", "playbook.yml", "--syntax-check")
		utils.chdir(cwd)
		utils.remove(tmpdir)
		utils.trace("check passed")

	def lint(self):
		for dirname, _, basenames in os.walk(TASKSDIR):
			for basename in basenames:
				_, extname = os.path.splitext(basename)
				if extname == ".yml":
					path = os.path.join(dirname, basename)
					utils.trace("linting '%s'" % path)
					tasks = unmarshall(path, default = []) or []
					for idx, play in enumerate(tasks):
						for manifest in utils.get_manifests(__path__):
							if not manifest["predicate"](play):
								name = play.get("name", "play#%i" % (idx + 1))
								sys.stderr.write(utils.yellow("warning! %s[%s]: %s\n") % (path, name, manifest["message"]))

	def check(self):
		self.check_syntax()
		self.lint()

	def _get_package_path(self):
		"return distribution package path"
		basename = "%s-%s.tgz" % (self.name, self.version)
		return os.path.join(DISTDIR, basename)

	def package(self):
		if not os.path.exists(DISTDIR):
			utils.mkdir(DISTDIR)
		utils.check_call("tar", "czf", self._get_package_path(), "--exclude", DISTDIR, ".")

	def publish(self, repository_url):
		if not repository_url:
			raise Error("no repository")
		utils.check_call(("curl", "-k", "-T", self._get_package_path(), repository_url))

	def distclean(self):
		for path in (MAINTASK_PATH, README_PATH, DISTDIR):
			if not path in self.excluded_paths and os.path.exists(path):
				utils.remove(path)

def main(args = None):
	opts = docopt.docopt(
		doc = __doc__,
		argv = args)
	try:
		if opts["--no-color"]:
			utils.disable_colors()
		if opts["--verbose"]:
			utils.enable_tracing()
		if opts["--directory"]:
			utils.chdir(opts["--directory"])
		role = Role((opts["--exclude"] or "").split(","))
		for target in opts["TARGET"]:
			{
				"init": role.init,
				"dist": role.dist,
				"check": role.check,
				"package": role.package,
				"publish": lambda: role.publish(opts["--repository"]),
				"distclean": role.distclean,
			}[target]()
	except (utils.Error, Error) as exc:
		raise SystemExit(utils.red(exc))
