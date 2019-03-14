

MAIL_FIFO_NAME="/tmp/mail-`date "+%Y%m%d%H%M%S"`"
MAIL_BODY_NAME="/tmp/mail-`date "+%Y%m%d%H%M%S"`"

function sendErrorMail(){
    pss=$1;
    sub=$2;
    msg=$3;
    python <<EOF
import smtplib
from email.mime.text import MIMEText
import sys


frm = "abhimondal@iitkgpmail.iitkgp.ac.in"
pss = "$pss"
to = "abhijitmanpur@gmail.com,abhimondal@iitkgp.ac.in"
sub = "$sub"
body = "$msg"


s = smtplib.SMTP("iitkgpmail.iitkgp.ac.in")
s.login("abhimondal", pss)
me="abhimondal@iitkgp.ac.in"

msg = MIMEText(open(body).read())
msg['From'] = me
msg['To'] = to
msg['Subject'] = sub
s.sendmail(me, to.split(","), msg.as_string())
s.quit()
EOF
   echo "Mail sent"
}

function waitnSendMail(){
    password=$1
    while true
    do
        body=$(cat $MAIL_FIFO_NAME)
        if [ "$body" == "stop" ]
        then
            echo "stoppped"
            rm $MAIL_FIFO_NAME
            rm ${MAIL_FIFO_NAME}.wait
            break
        fi
        if [ ! -f ${MAIL_FIFO_NAME}.mail ]
        then
            echo "================================="
            echo MAIL BODY NOT FOUND
            echo "================================="
        fi
        #echo $body > ${MAIL_FIFO_NAME}.mail,
        sendErrorMail $password "Error Mail" ${MAIL_FIFO_NAME}.mail
        rm ${MAIL_FIFO_NAME}.mail
        echo "done" > ${MAIL_FIFO_NAME}.wait
    done
}

function startSendMainDeamon(){
    stty -echo
    read -p "Your password: " password
    stty echo
    echo -n $password
    sleep 2
    printf "\r***********************************\n"
    echo $MAIL_FIFO_NAME
    mkfifo $MAIL_FIFO_NAME
    mkfifo ${MAIL_FIFO_NAME}.wait
    waitnSendMail $password &
    ret=$!
    echo $ret
    return $ret
}

function sendMailToRealEmail() {
            mailFile=${MAIL_FIFO_NAME}.test
            echo "$@" > $mailFile
            cat $mailFile > ${MAIL_FIFO_NAME}
            rm $mailFile
            cat ${MAIL_FIFO_NAME}.wait 
}

function myExit() {
    echo stop > $MAIL_FIFO_NAME
    exit $@
}

startSendMainDeamon

for x in ./videofilesizes/*.py
do
    fname=$(basename $x)
    for t in `seq 3`
    do
        #for sub in BOLA FastMPC RobustMPC Penseiv GroupP2PBasic GroupP2PTimeout
        for sub in GroupP2PTimeout GroupP2PBasic
        do
            echo python3 experiment_2.py $x powertest/$fname tc$t $sub 
            echo "===================================" > ${MAIL_FIFO_NAME}.mail
            echo python3 experiment_2.py $x powertest/$fname tc$t $sub >> ${MAIL_FIFO_NAME}.mail
            echo "===================================" >> ${MAIL_FIFO_NAME}.mail
            python3 experiment_2.py $x powertest/$fname tc$t $sub >> ${MAIL_FIFO_NAME}.mail 2>> ${MAIL_FIFO_NAME}.mail
            ret=$?
            if [ 0 -ne $ret ]
            then
                sendMailToRealEmail python3 experiment_2.py $x powertest/$fname tc$t $sub
                echo sent
            fi
            echo "================================="
            echo python3 experiment_2.py $x powertest/$fname tc$t $sub 
            echo "================================="
            sleep 10
            
            #rm ${MAIL_FIFO_NAME}.mail
            #myExit 0
        done
    done
done

myExit

