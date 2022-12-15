pipeline {
    agent {
        dockerfile {
            filename 'Dockerfile-build'

            // Since the build depends on the packaged tools and
            // documents, add --pull and --no-cache to ensure the
            // current packages are always used.
            additionalBuildArgs "--pull --no-cache --build-arg BRANCH=${params.BRANCH}"
        }
    }

    stages {
        stage('Build') {
            steps {
                sh './generate-html-docs.sh -b "$BRANCH"'
                sh './generate-index.py -b "$BRANCH"'
            }
        }

        stage('Publish') {
            steps {
                withCredentials([[$class: 'AmazonWebServicesCredentialsBinding',
                                  credentialsId: 'iam-user-jenkins-jobs',
                                  accessKeyVariable: 'AWS_ACCESS_KEY_ID',
                                  secretKeyVariable: 'AWS_SECRET_ACCESS_KEY']]) {
                    sh "./publish-docs.py -b ${params.BRANCH} --region ${params.REGION} ${params.DISTRIBUTION ? "--cloudfront ${params.DISTRIBUTION}" : ""} ${params.BUCKET}"
                }
            }
        }
    }
}
