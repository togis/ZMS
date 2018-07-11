// Plugins needed to execute this:
//  Pipeline
//  NodeJS
//  checkstyle
node('python27') {
    stage('Build27') {
        checkout scm
/*        sh "git clean -d -x -f"*/
/*        env.NODEJS_HOME = "${tool 'default-npm'}"*/
/*        env.PATH="${env.NODEJS_HOME}/bin:${env.PATH}"*/
/*        sh 'npm install'*/
        
/* TODO remove previous virtualenv if not done by repo cleanup */
        sh "virtualenv ./venv"
        sh "./venv/bin/pip install --upgrade setuptools"
        sh "./venv/bin/pip install --upgrade pip wheel"
        sh "./venv/bin/pip install --requirements requirements.txt"
        sh "./venv/bin/pip install --requirements selenium_tests/requirements.txt"
        sh "./venv/bin/pip install --requirements unit_tests/requirements.txt"
        sh "./venv/bin/pip install --editable ."
/* not required yet */
/*        sh "./venv/bin/python setup.py sdist"*/
/*        archiveArtifacts artifacts: 'dist/ZMS3-*.tar.gz', fingerprint: true*/
    }
/*    stage('jshint') {
        sh '$(npm bin)/jshint --extract=never --reporter=checkstyle . > data/testing/output/jshint_checkstyle.xml || true'
        checkstyle pattern: 'data/testing/output/jshint_checkstyle.xml'
    }
*/
    stage('Test27') {
        try {
            withEnv(['PATH+ZMS=./venv/bin']) {
                sh "./venv/bin/nosetests --processes 10 --with-xunit unit_tests || true"
            }
        } finally {
            junit '**/nosetests.xml'
        }
    }
    stage('AC Tests') {
        try {
            sh "~/bin/run_ac_tests"
        } finally {
            junit '**/junit.xml'
        }
    }
}
