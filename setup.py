from setuptools import setup, find_packages
from pathlib import Path

# Cargar el README como descripción larga
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

setup(
    name='tm1637-rpi5-gpiod',
    version='1.0.0',
    description='TM1637 4-digit display driver for Raspberry Pi 5 using gpiod',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='villeparamio',
    url='https://github.com/villeparamio/tm1637-rpi5-gpiod',
    license='MIT',
    packages=find_packages(),
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: POSIX :: Linux',
        'Intended Audience :: Developers',
        'Topic :: System :: Hardware :: Hardware Drivers',
    ],
    python_requires='>=3.7',
    install_requires=[
        'gpiod',
    ],
)
