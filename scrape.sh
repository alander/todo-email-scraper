#!/opt/local/bin/zsh

cd $HOME/projects/development/virtualenvs/todo-email-scraper
source bin/activate
cd src
python todo-email-scraper.py todo-email-scraper.rc
