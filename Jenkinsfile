pipeline {
   agent { dockerfile true }
   environment {
       registry = "audiofanjo/k8scicd"
       GOCACHE = "/tmp"
   }
   stages {
       stage('Build') {
           agent {
               docker {
                   image 'python:3.8-buster'
               }
           }
           steps {
               // Create our project directory.
               sh 'pip install -r requirements.txt'
           }
       }
       stage('Test') {
           agent {
               docker {
                   image 'python:3.8-buster'
               }
           }
           steps {
               // Create our project directory.
               sh 'python .homeassistant/__main__.py'
           }
       }
       stage('Publish') {
           environment {
               registryCredential = 'dockerhub'
           }
           steps{
               script {
                   def appimage = docker.build registry + ":$BUILD_NUMBER"
                   docker.withRegistry( '', registryCredential ) {
                       appimage.push()
                       appimage.push('latest')
                   }
               }
           }
       }
       stage ('Deploy') {
           steps {
               script{
                   def image_id = registry + ":$BUILD_NUMBER"
                   sh "ansible-playbook  playbook.yml --extra-vars \"image_id=${image_id}\""
               }
           }
       }
   }
}