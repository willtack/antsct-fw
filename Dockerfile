#flywheel/fmriprep

############################
# Get the image from DockerHub
FROM cookpa/antsct-aging:0.1.0

MAINTAINER Will Tackett <William.Tackett@pennmedicine.upenn.edu>

ENV ANTSCT_VERSION 0.1.0

############################
# Install basic dependencies
RUN apt-get update && apt-get -y install \
    jq \
    tar \
    zip \
    build-essential


############################
# Install the Flywheel SDK
RUN pip install flywheel-sdk
RUN pip install heudiconv
RUN pip install --upgrade fw-heudiconv ipython


############################
# Make directory for flywheel spec (v0)
ENV FLYWHEEL /flywheel/v0
RUN mkdir -p ${FLYWHEEL}
COPY run ${FLYWHEEL}/run
COPY prepare_run.py ${FLYWHEEL}/prepare_run.py
COPY manifest.json ${FLYWHEEL}/manifest.json
RUN chmod a+rx ${FLYWHEEL}/*

# Set the entrypoint
ENTRYPOINT ["/flywheel/v0/run"]

############################
# ENV preservation for Flywheel Engine
RUN env -u HOSTNAME -u PWD | \
  awk -F = '{ print "export " $1 "=\"" $2 "\"" }' > ${FLYWHEEL}/docker-env.sh

WORKDIR /flywheel/v0