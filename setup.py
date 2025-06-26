from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="5g-slice-manager",
    version="0.1.0",
    author="Ian Reuben Siangani",
    author_email="ireuben03@gmail.com",
    description="A comprehensive dashboard for managing 5G network slices",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/isiangani1/5G-network-manager",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "fastapi>=0.95.0",
        "uvicorn[standard]>=0.22.0",
        "sqlalchemy[asyncio]>=2.0.0",
        "asyncpg>=0.27.0",
        "python-dotenv>=1.0.0",
        "python-jose[cryptography]>=3.3.0",
        "passlib[bcrypt]>=1.7.4",
        "python-multipart>=0.0.6",
        "jinja2>=3.0.0",
        "aiofiles>=23.1.0",
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.9',
    entry_points={
        'console_scripts': [
            '5g-slice-manager=main:run',
        ],
    },
)
