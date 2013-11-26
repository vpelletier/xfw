from setuptools import setup
from os.path import join, dirname

description = open(join(dirname(__file__), 'README.rst')).read()

setup(
    name='xfw',
    version='0.10',
    description='eXtensible Fixed-Width file handling module',
    long_description='.. contents::\n\n' + description,
    keywords='fixed width field file',
    author='Nexedi',
    author_email='erp5-dev@erp5.org',
    url='http://git.erp5.org/gitweb/xfw.git',
    license='GPL 2+',
    platforms=["any"],
    py_modules=['xfw'],
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: Implementation :: PyPy',
        'Programming Language :: Python :: Implementation :: CPython',
    ],
    zip_safe=True,
)
