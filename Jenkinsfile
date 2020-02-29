pipeline {
    agent any

    parameters {
        string(name: 'BRANCH',
               description: 'OS branch',
               defaultValue: 'eos3a')
        string(name: 'TAG',
               description: 'Docker image tag',
               defaultValue: 'latest')
        booleanParam(name: 'FORCE',
                     description: 'Force build even if nothing changed',
                     defaultValue: false)
        booleanParam(name: 'DEBUG',
                     description: 'Show debugging messages',
                     defaultValue: false)
    }

    stages {
        stage('Build docs') {
            steps {
                sh '''\
                   #!/bin/bash -ex
                   ARGS=(-H https://ostree.endlessm-sf.com -b "$BRANCH")
                   "$FORCE" && ARGS+=(--force)
                   "$DEBUG" && ARGS+=(--debug)
                   ./build.sh "${ARGS[@]}"
                   '''.stripIndent()
            }
        }

        stage('Build docker image') {
            steps {
                script {
                    docker.build('endlessm/helpcenter:$TAG')
                }
            }
        }

        stage('Push docker image') {
            steps {
                script {
                    docker.withRegistry('', 'dockerhub-endlessci') {
                        docker.image('endlessm/helpcenter:$TAG').push()
                    }
                }
            }
        }
    }
}
