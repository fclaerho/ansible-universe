# copyright (c) 2015 fclaerhout.fr, released under the MIT license.

import unittest, os

import universe, fckit # 3rd-party

# files generated following 'init':
INITPATHS = ("meta/main.yml",)

# files generated following 'dist':
DISTPATHS = ("README.md", "tasks/main.yml")

class Test(unittest.TestCase):

	def _main(self, *args):
		universe.main(("-v", "-C", self.tmpdir) + args)

	def _assert_path_state(self, path, present = True):
		path = os.path.join(self.tmpdir, path)
		func = self.assertTrue if present else self.assertFalse
		func(os.path.exists(path), "%s: %s" % (
			path,
			"absent, expected present" if present else "present, expected absent"))

	def setUp(self):
		self.tmpdir = fckit.mkdir()
		self._main("init")
		map(self._assert_path_state, INITPATHS)

	def tearDown(self):
		fckit.remove(self.tmpdir)

	def test_check(self):
		self._main("check")
		map(self._assert_path_state, INITPATHS + DISTPATHS)

	def test_dist_clean(self):
		self._main("dist")
		map(self._assert_path_state, INITPATHS + DISTPATHS)
		self._main("clean")
		map(self._assert_path_state, INITPATHS)
		map(lambda path: self._assert_path_state(path, present = False), DISTPATHS)

	def test_package(self):
		self._main("package")
		map(self._assert_path_state, INITPATHS + DISTPATHS)
		path = os.path.join(self.tmpdir, ".build", "%s-0.0.1.tgz" % os.path.basename(self.tmpdir))
		self._assert_path_state(path)

if __name__ == "__main__": unittest.main(verbosity = 2)
