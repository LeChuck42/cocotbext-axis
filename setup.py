from setuptools import setup, find_namespace_packages

setup(name = 'cocotbext-EXTNAME',
	version = '0.1',
	packages = find_namespace_packages(include=['cocotbext.*']),
	install_requires = ['cocotb'],
	python_requires = '>=3.5',
	classifiers = [
		"Programming Language :: Python :: 3",
		"Operating System :: OS Independent",
		"Topic :: Scientific/Engineering :: Electronic Design Automation (EDA)"])