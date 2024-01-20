from setuptools import setup, find_packages

setup(
    name='scratchcommunication',
    version='2.0.0',
    author='Gine Mosild',
    author_email='thecommcraft@gmail.com',
    description='A python module for communicating with scratch projects',
    long_description='A python module for communicating with scratch projects',
    long_description_content_type='text/markdown',
    url='https://github.com/thecommcraft/scratchcommunication',
    packages=find_packages(exclude=[]),
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
    ],
    keywords=['scratch', 'api'],
    install_requires=[
        'requests',
        'websocket-client',
    ],
    python_requires='>=3.6',
)
