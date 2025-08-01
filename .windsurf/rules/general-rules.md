# Instructions

* The build system is uv. Add new packages using uv add.
* The main entry point is main.py
* The project is hosted on GitHub, Docker images are published for every push to main
* The project collects data from a source and publishes it via MQTT. There
  must be unit tests for the data transformation.
* The .env.template file for environment variables must be kept up to date.
* Env variables are defined in the .env file
* The following dependency must be used:
  * For publishing via MQTT: gcmb-publisher
  * HTTP client: requests
* The base MQTT topic is determined by environment variables: ${GCMB_ORG}/${GCMB_PROJECT}.
* topic-specific readmes in Markdown format are stored in the `gcmb` subfolder. Examples:
  * The readme for the topic ${GCMB_ORG}/${GCMB_PROJECT} is at `gcmb/README.md`
  * The readme for the topic ${GCMB_ORG}/${GCMB_PROJECT}/sometopic is at `gcmb/sometopic/README.md`
* Project-specific instructions can be found in the file project-instructions.md
