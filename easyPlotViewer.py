import sys
import json

class EasyPlot():
    def __init__(self):
        self.figs = [{"data" : [], "head" : ""}]
        self.seriesId = 0

    def printBegining(self, scripts, fp=sys.stdout):
        st = ""
        st += '<!DOCTYPE html>' + '\n'
        st += '<html>' + '\n'
        st += '<head>' + '\n'
        st += '    <meta http-equiv="Content-Type" content="text/html; charset=utf-8">' + '\n'
        st += '    <title>Network Activity</title>' + '\n'
        st += '<script language="javascript" type="text/javascript" src="https://rawgit.com/flot/flot/master/source/jquery.js"></script>' + '\n'
        st += '<script language="javascript" type="text/javascript" src="https://rawgit.com/flot/flot/master/https://rawgit.com/flot/flot/master/lib/jquery.event.drag.js"></script>' + '\n'
        st += '<script language="javascript" type="text/javascript" src="https://rawgit.com/flot/flot/master/https://rawgit.com/flot/flot/master/lib/jquery.mousewheel.js"></script>' + '\n'
        st += '<script language="javascript" type="text/javascript" src="https://rawgit.com/flot/flot/master/source/jquery.canvaswrapper.js"></script>' + '\n'
        st += '<script language="javascript" type="text/javascript" src="https://rawgit.com/flot/flot/master/source/jquery.colorhelpers.js"></script>' + '\n'
        st += '<script language="javascript" type="text/javascript" src="https://rawgit.com/flot/flot/master/source/jquery.flot.js"></script>' + '\n'
        st += '<script language="javascript" type="text/javascript" src="https://rawgit.com/flot/flot/master/source/jquery.flot.saturated.js"></script>' + '\n'
        st += '<script language="javascript" type="text/javascript" src="https://rawgit.com/flot/flot/master/source/jquery.flot.browser.js"></script>' + '\n'
        st += '<script language="javascript" type="text/javascript" src="https://rawgit.com/flot/flot/master/source/jquery.flot.drawSeries.js"></script>' + '\n'
        st += '<script language="javascript" type="text/javascript" src="https://rawgit.com/flot/flot/master/source/jquery.flot.errorbars.js"></script>' + '\n'
        st += '<script language="javascript" type="text/javascript" src="https://rawgit.com/flot/flot/master/source/jquery.flot.uiConstants.js"></script>' + '\n'
        st += '<script language="javascript" type="text/javascript" src="https://rawgit.com/flot/flot/master/source/jquery.flot.logaxis.js"></script>' + '\n'
        st += '<script language="javascript" type="text/javascript" src="https://rawgit.com/flot/flot/master/source/jquery.flot.symbol.js"></script>' + '\n'
        st += '<script language="javascript" type="text/javascript" src="https://rawgit.com/flot/flot/master/source/jquery.flot.flatdata.js"></script>' + '\n'
        st += '<script language="javascript" type="text/javascript" src="https://rawgit.com/flot/flot/master/source/jquery.flot.navigate.js"></script>' + '\n'
        st += '<script language="javascript" type="text/javascript" src="https://rawgit.com/flot/flot/master/source/jquery.flot.fillbetween.js"></script>' + '\n'
        st += '<script language="javascript" type="text/javascript" src="https://rawgit.com/flot/flot/master/source/jquery.flot.stack.js"></script>' + '\n'
        st += '<script language="javascript" type="text/javascript" src="https://rawgit.com/flot/flot/master/source/jquery.flot.touchNavigate.js"></script>' + '\n'
        st += '<script language="javascript" type="text/javascript" src="https://rawgit.com/flot/flot/master/source/jquery.flot.hover.js"></script>' + '\n'
        st += '<script language="javascript" type="text/javascript" src="https://rawgit.com/flot/flot/master/source/jquery.flot.touch.js"></script>' + '\n'
        st += '<script language="javascript" type="text/javascript" src="https://rawgit.com/flot/flot/master/source/jquery.flot.time.js"></script>' + '\n'
        st += '<script language="javascript" type="text/javascript" src="https://rawgit.com/flot/flot/master/source/jquery.flot.axislabels.js"></script>' + '\n'
        st += '<script language="javascript" type="text/javascript" src="https://rawgit.com/flot/flot/master/source/jquery.flot.selection.js"></script>' + '\n'
        st += '<script language="javascript" type="text/javascript" src="https://rawgit.com/flot/flot/master/source/jquery.flot.composeImages.js"></script>' + '\n'
        st += '<script language="javascript" type="text/javascript" src="https://rawgit.com/flot/flot/master/source/jquery.flot.legend.js"></script>' + '\n'
#         st += '    <script src="plugin/curvedLines.js"></script>' + '\n'
        st += '    <script type="text/javascript">' + '\n'
        print(st, file=fp)
        print(scripts, file=fp)
        st = '    </script>' + '\n'
        st += '</head>' + '\n'
        st += '<body>' + '\n'
        print(st, file=fp)

    def printEnding(self, fp=sys.stdout):
        st = ""
        st += "</body>" + "\n"
        st += "</html>"
        print(st, file=fp)

    def addFig(self):
        if len(self.figs[-1]["data"]) > 0:
            self.figs.append({"data" : [], "head" : ""})

    def setFigHeader(self, header):
        self.figs[-1]["head"] = header


    def plot(self, Xs, Ys, xaxis=1, yaxis=1, label="", color=None, toolTipData=None, *kw, **kws):
        rawData = list(zip(Xs, Ys))
        data = {
                "data" : rawData, \
                "label" : label, \
                "lines" : {"lineWidth": 2}, \
                "xaxis" : xaxis, \
                "yaxis" : yaxis, \
                "color" : color, \
                "clickable" : False, \
                "hoverable" : False,
               }
        self.figs[-1]["data"].append(data)
        data = {
                "data" : rawData, \
                "label" : label, \
                "points" : {"show": True, "radius" : 3},
                "lines" : {"show" : False},
                "xaxis" : xaxis, \
                "yaxis" : yaxis, \
                "color" : color, \
                "fillColor" : color,
                "pythondataseriesId": self.seriesId,
               }
        self.figs[-1]["data"].append(data)
        assert toolTipData == None or len(rawData) == len(toolTipData)
        if toolTipData != None:
            ttd = {"{:.6f}-{:.6f}".format(x,y):z for x,y,z in zip(Xs, Ys, toolTipData)}
            dt = self.figs[-1].setdefault("toolTipData", {}) 
            dt[self.seriesId] = ttd
        self.seriesId += 1

    def step(self, Xs, Ys, xaxis=1, yaxis=1, label=" ", color=None, toolTipData=None, where="pre", *kw, **kws):
        rawData = list(zip(Xs, Ys))
        preXs = Xs[:-1]
        preYs = Ys[:-1]
        postXs = Xs[1:]
        postYs = Ys[1:]

        preData = []
        postData = []
        for i, dt in enumerate(rawData):
            x, y = dt
            if i > 0:
                preData += [(Xs[i-1], y)]
            preData += [(x, y)]
            postData += [(x, y)]
            if i < len(rawData)-1:
                postData += [(Xs[i+1], y)]

        stepData = preData
        if where == "post":
            stepData = postData
        data = {
                "data" : stepData, \
                "label" : label, \
                "lines" : {"shadowSize" : 0, "lineWidth": 2}, \
                "xaxis" : xaxis, \
                "yaxis" : yaxis, \
                "color" : color, \
                "clickable" : False, \
                "hoverable" : False,
               }
        self.figs[-1]["data"].append(data)
        data = {
                "data" : rawData, \
                "label" : label, \
                "points" : {"show": True, "radius" : 3},
                "lines" : {"show" : False},
                "xaxis" : xaxis, \
                "yaxis" : yaxis, \
                "color" : color, \
                "fillColor" : color,
                "pythondataseriesId": self.seriesId,
               }
        self.figs[-1]["data"].append(data)

        assert toolTipData == None or len(rawData) == len(toolTipData)
        if toolTipData != None:
            ttd = {"{:.6f}-{:.6f}".format(x,y):z for x,y,z in zip(Xs, Ys, toolTipData)}
            dt = self.figs[-1].setdefault("toolTipData", {}) 
            dt[self.seriesId] = ttd
        self.seriesId += 1

    def figEnclosure(self, st):
        return st

    def printFigs(self, fp=sys.stdout, figEnclosure=None, width=600, height=200, *kw, **kws):
        figEnclosure = self.figEnclosure
        options = { \
#                 "xaxis" : [{"position" : "top"}], \
#                 "yaxis" : [{"position" : "left"}, { "position" : "right"}], \
                "grid" : { \
                    "hoverable" : True, \
                    "clickable" : True, \
                    }, \
#                 "zoom" : { \
#                     "interactive" : True \
#                         }, \
#                 "pan" : { \
#                     "interactive" : True,
#                     "enableTouch": True
#                     }, \
#                 "selection" : { \
#                     "mode" : "xy" \
#                     } \
                }
        datas = "datas = {\n"
        toolTipData = "toolTipData = {\n"
        script = ""
        script += "    $(function() {" + '\n'
        script += "     function doPlot() {" + '\n'
        for fig in self.figs:
            script +='$.plot("#EasyPlotPlaceHolder_' + str(id(fig)) + '", \n' 
            script += '\t\tdatas["EasyPlotPlaceHolder_' + str(id(fig)) + '"], \n'
            script += "\t\t" + json.dumps(options)
            script += ");\n"

            datas += '"EasyPlotPlaceHolder_' + str(id(fig)) + '": ' + json.dumps(fig["data"]) + ", \n"
            if "toolTipData" in fig:
                toolTipData += '"EasyPlotPlaceHolder_' + str(id(fig)) + '": ' + json.dumps(fig["toolTipData"]) + ", \n"

        datas += "}\n"
        toolTipData += "}\n"

        script += "     }" + '\n'

        script += "     doPlot()" + '\n'

        script += '     pltOptions = {}' + '\n'
        script += '     homeOption = ' + json.dumps(options) + '\n'
        script += '     ' + '\n'
        script += '     $(".demo-placeholder").bind("plotselected", function (event, ranges) {' + '\n'
        script += '        if (ranges.xaxis.to - ranges.xaxis.from < 0.00001) {' + '\n'
        script += '                ranges.xaxis.to = ranges.xaxis.from + 0.00001;' + '\n'
        script += '            }' + '\n'
        script += '        id = $(this).attr("id")' + '\n'
        script += '        option = pltOptions[id]' + '\n'
        script += '        option["xaxis"] = { min: ranges.xaxis.from, max: ranges.xaxis.to, autoScale: "none" }' + '\n'
        script += '        console.log(JSON.stringify(option))' + '\n'
        script += '        $.plot("#"+id, datas[id], option)' + '\n'
        script += '        pltOptions[id] = option' + '\n'
        script += '     })' + '\n'
        script += '' + '\n'
        script += '     $(".home").click(function(){' + '\n'
        script += '        id = $(this).attr("data-pltId")' + '\n'
        script += '        $.plot("#"+id, datas[id], homeOption)' + '\n'
        script += '        pltOptions[id] = homeOption' + '\n'
        script += '     })' + '\n'
        script += '' + '\n'
        script += '     $(".demo-placeholder").each(function(){' + '\n'
        script += '        id = $(this).attr("id")' + '\n'
        script += '        pltOptions[id] = $.extend(true, {}, homeOption)' + '\n'
        script += '     })' + '\n'
        script += '' + '\n'
        script += '     $(".zoom").click(function(){' + '\n'
        script += '        id = $(this).attr("data-pltId")' + '\n'
        script += '        text = $(this).text()' + '\n'
        script += '        option = pltOptions[id]' + '\n'
        script += '        if (text == "Enable Zoom"){' + '\n'
        script += '            option["selection"] = {mode:"x"}' + '\n'
        script += '            $(this).text("Disable Zoom")' + '\n'
        script += '        }' + '\n'
        script += '        else{' + '\n'
        script += '            option["selection"] = ""' + '\n'
        script += '            $(this).text("Enable Zoom")' + '\n'
        script += '        }' + '\n'
        script += '        $.plot("#"+id, datas[id], option)' + '\n'
        script += '        pltOptions[id] = $.extend(true, {}, option)' + '\n'
        script += '     })' + '\n'
        script += '' + '\n'
        script += '     $(".pan").click(function(){' + '\n'
        script += '        id = $(this).attr("data-pltId")' + '\n'
        script += '        text = $(this).text()' + '\n'
        script += '        option = pltOptions[id]' + '\n'
        script += '        if (text == "Enable Pan"){' + '\n'
        script += '            option["pan"] = ' + json.dumps({"interactive" : True, "enableTouch": True }) + '\n'
        script += '            $(this).text("Disable Pan")' + '\n'
        script += '        }' + '\n'
        script += '        else{' + '\n'
        script += '            option["pan"] = ""' + '\n'
        script += '            $(this).text("Enable Pan")' + '\n'
        script += '        }' + '\n'
        script += '        $.plot("#"+id, datas[id], option)' + '\n'
        script += '        pltOptions[id] = $.extend(true, {}, option)' + '\n'
        script += '     })' + '\n'

        script += '     $("<div id=\'tooltip\'></div>").css({' + '\n'
        script += '            position: "absolute",' + '\n'
        script += '            display: "none",' + '\n'
        script += '            border: "1px solid #fdd",' + '\n'
        script += '            padding: "2px",' + '\n'
        script += '            "background-color": "#fee",' + '\n'
        script += '            opacity: 0.80' + '\n'
        script += '        }).appendTo("body");' + '\n'
        script += '' + '\n'
        script += '        $(".demo-placeholder").bind("plothover", function (event, pos, item) {' + '\n'
        script += '            id = $(this).attr("id")' + '\n'
        script += '' + '\n'
        script += '            if (item) {' + '\n'
        script += '                var x = item.datapoint[0].toFixed(6),' + '\n'
        script += '                    y = item.datapoint[1].toFixed(6);' + '\n'
        script += '                tooltipLabel = item.series.label + " of " + x + " = " + y' + '\n'
        script += '                pythonSeriesId = item.series.pythondataseriesId' + '\n'
        script += '                if (id in toolTipData && pythonSeriesId in toolTipData[id]){' + '\n'
        script += '                    if (x + "-" + y in toolTipData[id][pythonSeriesId]){' + '\n'
        script += '                var xs = item.datapoint[0].toFixed(2),' + '\n'
        script += '                    ys = item.datapoint[1].toFixed(2);' + '\n'
        script += '                        tooltipLabel = xs + ":" + ys + ":"  + toolTipData[id][pythonSeriesId][x + "-" + y]' + '\n'
        script += '                    }' + '\n'
        script += '                }' + '\n'
        script += '                $("#tooltip").html(tooltipLabel)' + '\n'
        script += '                    .css({top: item.pageY+5, left: item.pageX+5})' + '\n'
        script += '                    .fadeIn(200);' + '\n'
        script += '            } else {' + '\n'
        script += '                $("#tooltip").hide();' + '\n'
        script += '            }' + '\n'
        script += '' + '\n'
        script += '        });' + '\n'
        script += '        $(".demo-placeholder").bind("plothovercleanup", function (event, pos, item) {' + '\n'
        script += '                $("#tooltip").hide();' + '\n'
        script += '        });' + '\n'

        script += "})" + '\n'

        script = datas + toolTipData + script
        self.printBegining(script, fp)

        for fig in self.figs:
            st = str(fig["head"])
            st += '    <div id="EasyPlotPlaceHolder_' + str(id(fig)) + '" class="demo-placeholder" style="width:'+str(width)+'px;height:'+str(height)+'px"></div>' + "\n"
            st += '<input type="text" class="xrange" data-pltId="EasyPlotPlaceHolder_' + str(id(fig)) + '">'
            st += '<button class="home" data-pltId="EasyPlotPlaceHolder_' + str(id(fig)) + '">Home</button>'
            st += '<button class="zoom" data-pltId="EasyPlotPlaceHolder_' + str(id(fig)) + '">Enable Zoom</button>'
            st += '<button class="pan" data-pltId="EasyPlotPlaceHolder_' + str(id(fig)) + '">Enable Pan</button>'
            print(figEnclosure(st, *kw, **kws), file=fp)

        self.printEnding(fp)


if __name__ == "__main__":
    p = EasyPlot()
    p.plot([0,1,2,3], [0,1,2,3,])
    p.step([0,1,2,3], [0,1,2,3,])
    p.addFig()
    p.plot([0,1,2,3], [0,1,2,3,])
    p.step([0,1,2,3], [0,1,2,3,])
    p.printFigs()
