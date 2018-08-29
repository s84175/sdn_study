# ryu 環境設定
sudo apt-get install python-pip python-dev -y 

sudo apt-get install libxml2-dev libxslt1-dev python-eventlet python-routes python-webob python-paramiko -y

sudo pip install oslo.config

sudo pip install msgpack-python

sudo git clone https://github.com/osrg/ryu.git

cd ryu

sudo python ./setup.py install

sudo pip install tinyrpc

sudo pip install -r tools/pip-requires

sudo python setup.py install

sudo ryu-manager
