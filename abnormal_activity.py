#!/usr/bin/env python2
# -*- coding: UTF-8 -*-

from flask import Flask, request, render_template, jsonify
from plot_event import *
import json, time
app = Flask(__name__)

CONFIG_PATH = "config.json"

g_map_video_actions = {}
g_plot_data         = {}

g_initialized = False

g_log_path = ""
g_benchmark_url = "http://icc-benchmark.momenta.works/case/single/"

@app.route('/')
def index():
    return render_template("index.html")

@app.route('/plot', methods=['GET'])
def plot():
    global g_map_video_actions
    global g_plot_data
    action_name = request.args.get('action_name').strip()
    video_name = request.args.get('video_name').strip()

    if video_name not in g_plot_data.keys():
        return jsonify({'status': '-1', "msg":"video_name not exists !!!"})
    if action_name not in g_plot_data[video_name].keys():
        return jsonify({'status': '-1', "msg":"action_name not contained in the video !!!"})

    video_data  = g_plot_data[video_name][action_name]

    save_path = "static/" + video_name + "-" + action_name + ".png"
    video_path = g_benchmark_url + video_name

    if action_name == ACTION_NAME_EYE_CLOSE:
        plot_eye_close(video_data, ATTR_FRAME_ID, ATTR_SCORE, save_path)
    else:
        plot_normal_action(video_data, ATTR_FRAME_ID, ATTR_SCORE, save_path)

    return jsonify({'status': '0', "video_path":video_path, "img_path":save_path})

def initialize():
    print("initialize ...")

    global g_map_video_actions
    global g_plot_data
    global g_initialized
    global g_log_path
    global g_benchmark_url
    if g_initialized:
        return
    f = open(CONFIG_PATH)
    data = f.read()
    f.close()
    jsonobj = json.loads(data)
    g_log_path = jsonobj["path"]
    g_benchmark_url = jsonobj["url"]

    time0 = int(time.time()*1000)

    map_video_jsonlist  = load_log_file(g_log_path)
    time1 = int(time.time()*1000)
    print("load_log_file cost: %d ms" % (time1 - time0))

    g_map_video_actions = normalize_json_data(map_video_jsonlist)
    time2 = int(time.time()*1000)
    print("normalize_json_data cost: %d ms" % (time2 - time1))

    merge_eyeclose_data(g_map_video_actions)
    time3 = int(time.time()*1000)
    print("merge_eyeclose_data cost: %d ms" % (time3 - time2))

    g_plot_data         = normalize_plot_data(g_map_video_actions)
    time4 = int(time.time()*1000)
    print("normalize_plot_data cost: %d ms" % (time4 - time3))

    print("initialize okay.")  

if __name__ == '__main__':
    initialize()
    app.run(host='0.0.0.0', port=80, debug=False)