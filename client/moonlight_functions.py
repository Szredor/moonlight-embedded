import subprocess
import time
import logging
import logging.config
import random

from resources import Package

logging.config.fileConfig("logs/log.conf", disable_existing_loggers=False)
log = logging.getLogger(__name__)


def moonlight_command(cmd, timeout):
    log.debug("executing command: %s", cmd)
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    start_time = time.time()
    timeout_time = start_time + timeout
    out = ""

    while time.time() < timeout_time:
        if process.poll() == 0:
            break
        
    if time.time() >= timeout_time:
        process.terminate()
        log.debug("TIMEOUT")
        return None
    else:
        end = False
        while not end:
            ch = process.stdout.read(1)
            
            if ch != b'':
                out = out + ch.decode()
            else:
                end = True
        
        log.debug("with output:\n%s", out)
        return out


def send_pair_request(dom_ip, output):
    log.info("sending pair request")
    process = subprocess.Popen(["./moonlight-embedded-KSM/moonlight", "pair", dom_ip], stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    
    start_time = time.time()
    timeout = 3
    timeout_time = start_time + timeout    
    
    while time.time() < timeout_time:
        if process.poll() == 0:
            break
    
    if time.time() >= timeout_time:
        process.terminate()
        output.append("TIMEOUT")
    else:
        stderr = process.stderr.readline()
        if stderr != b'':
            output.append(stderr.decode())

    if len(output) == 0:
        output.append("PAIRED")

    log.debug(output[0])


def unpair():
    log.info("Unpairing with gaming domain")
    process = subprocess.run(["./moonlight-embedded-KSM/moonlight", "unpair"], stderr=subprocess.PIPE, stdout=subprocess.PIPE)


def randomize_code():
    code = random.randint(1e3, 1e4)

    with open("moonlight-embedded-KSM/recent-code.txt", "w") as f:
        f.write(str(code))
    log.debug("code randomized: %d", code)
    return code


def get_pair_code():
    with open("moonlight-embedded-KSM/recent-code.txt", "r") as f:
        code = f.readline()
    return code


def list_available_games(dom_ip):
    log.info("getting list of available games")
    out = moonlight_command(["./moonlight-embedded-KSM/moonlight", "list", dom_ip], 10)
    if out is None:
        log.debug("there are no games")
        return None
    
    out = out.split('\n')
    game_list_raw = out[1:-1]
    game_list = []
    for line in game_list_raw:
        cut = line.find(" ")
        game_list.append(line[cut+1:])
    
    log.debug("list of games:\n%s", game_list)
    return game_list


def stream_game(name, dom_ip):
    log.info("streaming game: %s", name)
    log.info("Running command: ./moonlight-embedded-KSM/moonlight stream -app %s -bitrate 51200 %s", name, dom_ip)
    process = subprocess.run(["./moonlight-embedded-KSM/moonlight", "stream", "-app", name, "-bitrate", "51200", "-1080", "-fps", "60", dom_ip], stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    log.info("Running command: ./moonlight-embedded-KSM/moonlight quit %s", dom_ip)
    process = subprocess.run(["./moonlight-embedded-KSM/moonlight", "quit", dom_ip], stderr=subprocess.PIPE, stdout=subprocess.PIPE)
