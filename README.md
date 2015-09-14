
**Ansible-universe** is an [Ansible role](http://docs.ansible.com/ansible/playbooks_roles.html) build tool supporting the following features:
  * platform check generation
  * role syntax check & linter
  * proper `README.md` generation
  * packaging & publishing into private web repositories

**Ansible-universe** understands the following targets:
  * `init` instantiate role template
  * `dist` generate ansible distributable role files
  * `check` include role in a dummy playbook and check syntax
  * `package` package role
  * `publish -r…` publish role to a web repository
  * `distclean` delete generated files


Build Manifest
--------------

**Ansible-universe** uses the ansible-galaxy manifest, `meta/main.yml`, with the following additional attributes:
  * `version`, defaults to 0.0.1
  * `variables`, maps names to descriptions
  * `inconditions`, maps tasks filename to include conditions

On build, two files are generated:
  * `tasks/main.yml`, performing the platform check and including any other .yml file in tasks/
    Conditions to inclusions can be specified via the `inconditions` attribute of the manifest.
  * `README.md`, gathering the role description, supported platforms and data on variables.


Example
-------

	$ mkdir foo
	$ ansible-universe -C foo init dist check


Installation
------------

	$ pip install --user ansible-universe

or, if the PyPI repository is not available:

	$ pip install --user git+https://github.com/fclaerho/ansible-universe.git

The package will be installed in your [user site-packages](https://www.python.org/dev/peps/pep-0370/#specification) directory; make sure its `bin/` sub-directory is in your shell lookup path.

To uninstall:

	$ pip uninstall ansible-universe


Linter Development
------------------

The builtin linter can easily be extended with your own checks:
  * in the universe directory, create a new module defining the `MANIFEST` dict
  * in `__init__.py`, register that new module in the `MANIFESTS` dict

The `MANIFEST` global has two attributes:
  * `message`, the message to display when the check fails
  * `predicate`, the callback to use to do the actual check;
     it should take a single argument `play` corresponding to the play being linted.
