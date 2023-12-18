from setuptools import setup
setup(
    name = 'eml2text',
    version = '0.1.0',
    packages = ['eml2text'],
    entry_points = {
        'console_scripts': [
            'eml2text = eml2text.__main__:main'
        ]
    })
