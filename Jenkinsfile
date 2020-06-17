pipeline {
    agent {
        dockerfile {
            filename 'Dockerfile-build'
            additionalBuildArgs "--build-arg BRANCH=${params.BRANCH}"
        }
    }

    stages {
        stage('Build') {
            steps {
                sh './generate-html-docs.sh'
                sh './generate-index.py'
            }
        }

        stage('Publish') {
            steps {
                withCredentials([[$class: 'AmazonWebServicesCredentialsBinding',
                                  credentialsId: 'iam-user-jenkins-jobs',
                                  accessKeyVariable: 'AWS_ACCESS_KEY_ID',
                                  secretKeyVariable: 'AWS_SECRET_ACCESS_KEY']]) {
                    sh "./publish-docs.sh --region ${params.REGION} ${params.BUCKET}"
                }
            }
        }
    }
}
