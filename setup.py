#!/usr/bin/env python
import os, json, pprint, sys, shutil, subprocess, tarfile

from setuptools import setup
from distutils.command.build import build as _build
from distutils.command.clean import clean as _clean
from distutils.command.sdist import sdist as _sdist
# check FuzzEd/__init__.py for the project version number
from FuzzEd import __version__, util

IS_WINDOWS = os.name == 'nt'
FILE_EXTENSION = '.py' if IS_WINDOWS else ''
FILE_PREFIX = 'file:///' + os.getcwd() + '/' if IS_WINDOWS else '' 


def build_xmlschema_wrapper():
    print 'Building XML schema wrappers ...'

    # Remove old binding files and generate new ones
    for file_name in ['xml_faulttree.py', 'xml_fuzztree.py', 'xml_analysis.py']:
        path_name = 'FuzzEd/models/%s' % file_name

        if os.path.exists(path_name):
            os.remove(path_name)
    if os.system('pyxbgen%s --binding-root=FuzzEd/models/ -u %sFuzzEd/static/xsd/analysis.xsd '
                 '-m xml_analysis -u %sFuzzEd/static/xsd/fuzztree.xsd -m xml_fuzztree -u %sFuzzEd/static/xsd/faulttree.xsd -m xml_faulttree'
                 % (FILE_EXTENSION, FILE_PREFIX, FILE_PREFIX, FILE_PREFIX,)) != 0:
        raise Exception('Execution of pyxbgen failed.\nTry "sudo setup.py test" for installing all dependencies.')

def build_django_require():
    print 'Building compressed static files ...'
    # Use Django collectstatic, which triggers django-require optimization
    if os.system('./manage.py collectstatic -v3 --noinput') != 0:
        raise Exception('Execution of collectstatic failed. Please check the previous output.\n'
                        'Try "sudo setup.py test" for installing all dependencies.')

def build_notations():
    notations_dir = 'FuzzEd/static/notations/'
    file_list = os.listdir(notations_dir)
    notations = []

    for file_path in [os.path.join(notations_dir, file_name) for file_name in file_list]:
        if os.path.isfile(file_path) and file_path.endswith('.json'):

            with open(file_path) as handle:
                notations.append(json.loads(handle.read()))
    resolve_inheritance(notations)

    out=open('FuzzEd/models/notations.py', 'w')
    out.write('# DO NOT EDIT! This file is auto-generated by "setup.py build"\n')
    out.write('notations = ')
    pprint.pprint(notations, out)
    out.write('\nby_kind = {notation[\'kind\']: notation for notation in notations}\n')
    out.write('choices = ')
    pprint.pprint(generate_choices(notations), out)
    out.write('\nnode_choices = ')
    pprint.pprint(generate_node_choices(notations), out)
    out.write('\n# END OF GENERATED CONTENT')

def generate_choices(notations):
    return [(notation['kind'], notation['name']) for notation in notations]

def generate_node_choices(notations):
    node_choices = []

    for notation in notations:
        nodes = notation['nodes']
        node_category = (notation['name'],)
        node_category_choices = ()

        for node_kind, node in nodes.items():
            node_category_choices += ((node_kind, node['nodeDisplayName']),)

        node_category += (node_category_choices,)
        node_choices.append(node_category)

    return node_choices

def resolve_inheritance(notations):
    for notation in notations:
        nodes = notation['nodes']
        node_cache = {}

        for node_name, node in nodes.items():
            nodes[node_name] = inherit(node_name, node, nodes, node_cache)

def inherit(node_name, node, nodes, node_cache):
    inherits_from = node.get('inherits')

    if not inherits_from:
        node_cache[node_name] = node
        return node

    elif inherits_from not in node_cache:
        inherit(inherits_from, nodes[inherits_from], nodes, node_cache)

    resolved = util.extend({}, node_cache[inherits_from], node, deep=True)
    node_cache[node_name] = resolved

    return resolved

# Our overloaded 'setup.py build' command
class build(_build):
    def run(self):
        _build.run(self)
        build_analysis_server()
        build_notations()
        build_schema_files()
        build_xmlschema_wrapper()
        build_shape_lib()

# Our overloaded 'setup.py clean' command
class clean(_clean):
    def run(self):
        _clean.run(self)
        clean_docs()
        clean_pycs()
        clean_build_garbage()


# Our overloaded 'setup.py sdist' command
class sdist(_sdist):
    def run(self):
        build_naturaldocs()
        build_django_require()
        # keep the settings_local on this machine and
        # prepare the one for the production system
        try:
            shutil.move('FuzzEd/settings_local.py','FuzzEd/settings_local.py.backup')
        except:
            pass
        shutil.copyfile('FuzzEd/settings_production.py','FuzzEd/settings_local.py')
        _sdist.run(self)  # file collection based on MANIFEST.IN for FuzzEd release
        os.remove('FuzzEd/settings_local.py')
        try:
            shutil.move('FuzzEd/settings_local.py.backup','FuzzEd/settings_local.py')
        except:
            pass
        sdist_analysis_server()
        sdist_rendering_server()

setup(
    name = 'FuzzEd',
    version = __version__,
    packages = ['FuzzEd'],
    include_package_data = True,
    cmdclass={
        'build': build,
        'clean': clean,
        'sdist': sdist
    },
    maintainer = 'Peter Troeger',
    maintainer_email = 'peter.troeger@hpi.uni-potsdam.de',
	url = 'https://bitbucket.org/troeger/fuzztrees'
)
