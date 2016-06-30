#!/usr/bin/env python
# -*- coding: utf-8 -*-


from setuptools import setup, find_packages

requirements = [
    'cffi>=1.6.0',
    'setuptools>=5.5.1',
    'cryptography>=1.3.2',
    'requests>=2.4.3',
    'netaddr>=0.7.18',
    'markupsafe>=0.23',
    'pyyaml>=3.11',
    'boto>=2.40.0',
    'apache-libcloud>=0.20.1'
]

test_requirements = [
    # TODO: put package test requirements here
]

setup(
    name='kargo',
    version='0.4.0',
    description="Kargo kubernetes cluster deployment",
    author="Smaine Kahlouch",
    author_email='smainklh@gmail.com',
    url='https://github.com/kargo/kargo',
    data_files=[
        ('/etc/kargo', ['src/kargo/files/kargo.yml'])
    ],
    packages=find_packages('src'),
    scripts=[
        'bin/kargo'
    ],
    package_dir={'': 'src'},
    package_data={'kargo': ['files/*.yml'], },
    install_requires=requirements,
    license="GPLv3",
    zip_safe=False,
    keywords='kargo',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'Natural Language :: English',
        "Programming Language :: Python :: 2",
        'Programming Language :: Python :: 2.7',
    ],
    test_suite='tests',
    tests_require=test_requirements
)
