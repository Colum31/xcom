from setuptools import setup

setup(
    name='xcom',
    version='3.7',
    packages=['xcom'],
    author='Colum31',
    url='https://github.com/Colum31/xcom',
    description='xcom is a simple command-line utility, to interface with serial devices.',
    install_requires=[
        'pyserial'
    ],
    entry_points={
        "console_scripts": ['xcom=xcom.xcom_main:main'],
    }
)
