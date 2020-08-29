import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="spotify-telegram-sync",
    version="0.0.1",
    author="Hazhir",
    author_email="a.hazhir@gmail.com",
    description="Sync your Spotify playlist with a Telegram channel",
    long_description=long_description,
    long_description_content_type="text/markdown",
    # url="https://github.com/pypa/sampleproject",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: CC BY-NC-SA 4.0",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)
