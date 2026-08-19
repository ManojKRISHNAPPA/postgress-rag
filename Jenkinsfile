pipeline{
    agent any

    environment {
        IMAGE_NAME = "manojkrishnappa/postgress-rag-dev:${GIT_COMMIT}"
    }

    stages{
        stage('git-checkout'){
            steps{
                git branch: 'main', url: 'https://github.com/ManojKRISHNAPPA/postgress-rag.git'  
            }    
        }

        stage('docker-build'){
            steps{
                script{
                    sh '''
                    printenv
                    docker build -t ${IMAGE_NAME} .
                    '''
                }
            }
        }

        stage('docker-login'){
            steps{
                withCredentials([usernamePassword(credentialsId: 'dockerhub-creds', passwordVariable: 'DOCKER_PASSWORD', usernameVariable: 'DOCKER_USERNAME')]) {
                    sh '''
                    echo $DOCKER_PASSWORD | docker login -u $DOCKER_USERNAME --password-stdin
                    '''
                }
            }
        }

        stage('docker-push'){
            steps{
                sh '''
                docker push ${IMAGE_NAME}
                '''
            }
        }
    }

}