# -*- coding: utf-8 -*-
"""
Created on Sat Nov 23 10:46:14 2019

@author: clips
"""
import json
import webvtt
    
class VideoCaption(object):
    """
    Test grouping sentences from  VTT
    Read file using: WebVTT().read_cdp('captions.vtt' )
    """

    def __init__(self, file='', styles=None):
        self.file = file
        self._captions = []
        self._styles = styles # raw, none

    def readFiles(self):
        for caption in webvtt.WebVTT().read_cdp( self.file ):
            print(caption.start)
            print(caption.end)
            print( caption.text )
            self._captions.append( caption.text )
            
    def exportToJson(self):
        #Check that this works with other dict
        with open('personalCaptions.json', 'w') as json_file:
            json.dump(self._captions, json_file)
            
        
if __name__ == "__main__":
    vid = "D:/Hacktogivethanks/webvtt-py/videocaptionsraw/video.vtt"
    v = VideoCaption( vid )
    v.readFiles()
    v.exportToJson()
    
    
    