from setuptools import setup, find_packages

with open("README.md", encoding="utf-8") as f:
    long_description = f.read()
    
VERSION = '2.11.2'

setup(
    name='scratchcommunication',
    version=VERSION,
    author='Simon Gilde',
    author_email='simon.c.gilde@gmail.com',
    description='A python module for communicating with scratch projects',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/thecommcraft/scratchcommunication',
    packages=find_packages(exclude=[]),
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Programming Language :: Python :: 3.13',
    ],
    keywords=['scratch', 'api'],
    install_requires=[
        'requests',
        'websocket-client',
        'func-timeout',
        'pycryptodome',
        'attrs',
        'browsercookie',
        'cryptography'
    ],
    python_requires='>=3.11',
)
