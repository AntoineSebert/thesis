# Metaheuristic Extensibility Scheduling

## Description

This project aims to deliver a static scheduler that maximizes the amount of time that can be dynamically allocated for sporadic tasks.

We will be comparing [Approach A] and [Approach B], in a hybrid real-time system composed of heterogeneous fog nodes and providing a global notion of time. Moreover, tasks may have data dependencies, which are modeled using a directed acyclic graph (DAG), where nodes are tasks and edges represent data flows between the tasks.

Our program takes scheduling problems (FCP description and task set), formalized with a dedicated XML schema, as input, and outputs a task graph representing the solution.

The project primarily targets embedded systems with strong real-time requirements and a need for processing unexpected tasks. Critical software for cars or airplanes, or  IoT devices  within the Fog Computing paradigm are expected to benefit from our work.

The final objective is to increase Quality of Service (QoS) of Fog Computing Platforms (FCP) with best-suitable methods for Extensible Scheduling during the design process.

## Getting started

### Prerequisites

This project has been created with *Python 3.8.5* and [Poetry](https://github.com/python-poetry/poetry) for the packaging. We strongly advice using it with *Python 3.8.x* to avoid unecessary issues.

*Note for the unfortunate Microsoft Windows users : you may want to set the default system encoding to UTF-8, see [here](https://docs.python.org/3/using/cmdline.html#envvar-PYTHONUTF8).*

### Installation

Simply clone the repository :
```bash
git clone https://github.com/AntoineSebert/thesis
```

Set the installation directory as the working directory :
```bash
cd thesis
```

Install the dependencies :
```bash
poetry install
```

### Running the program and the test suite

The test suite can be launched with :
```bash
poetry run python tests.py
```

Finally, run the program :
```bash
poetry run python src/main.py --help
```

## Contributions

*Disclaimer*
Since this project is realized as a thesis project, no PRs concerning important features can be accepted, at least until the end of the thesis (hopefully mid-2021).

If you want to get involved, see [CONTRIBUTING.md](CONTRIBUTING.md).
We use [SemVer](https://semver.org/) for versioning, and [flake8](https://gitlab.com/pycqa/flake8) for formatting.
Please note that I also have a [Code of Conduct](CODE_OF_CONDUCT.md).

## License

This project is licensed under the Mozilla Public License 2.0, that you can find in [LICENSE](LICENSE).

## Authors

[Antoine/Anthony Sébert](https://github.com/AntoineSebert) - Code

## Acknowledgments

No.