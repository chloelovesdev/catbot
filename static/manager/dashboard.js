var socket = new WebSocket("ws://" + window.location.host + "/manage/" + botID + "/output");

var term = new Terminal();

function getIdealSize(e) {
    if (!e.element.parentElement) return null;
    var t = window.getComputedStyle(e.element.parentElement),
        r = parseInt(t.getPropertyValue("height")),
        o = Math.max(0, parseInt(t.getPropertyValue("width"))),
        n = window.getComputedStyle(e.element),
        i = r - (parseInt(n.getPropertyValue("padding-top")) + parseInt(n.getPropertyValue("padding-bottom"))),
        l = o - (parseInt(n.getPropertyValue("padding-right")) + parseInt(n.getPropertyValue("padding-left"))) - e._core.viewport.scrollBarWidth;
    return {
        cols: Math.floor(l / e._core._renderCoordinator.dimensions.actualCellWidth),
        rows: Math.floor(i / e._core._renderCoordinator.dimensions.actualCellHeight)
    }
}

function resizeTerminal(term) {
    var idealSize = getIdealSize(term);
    idealSize.rows = 25;

    if (idealSize) {
        if(term.rows !== idealSize.rows || term.cols !== idealSize.cols){
            term._core._renderCoordinator.clear();
            term.resize(idealSize.cols, idealSize.rows);
        }
    }
}

$(window).resize(function(){
    resizeTerminal(term);
});

term.open($("#bot-output")[0]);
resizeTerminal(term);

socket.addEventListener('message', function (event) {
    term.write(event.data + "\r\n");
});

$("#start").click(function() {
    $.get( "/manage/" + botID + "/start", function( data ) {
        if(data.success) {
            new Noty({
              text: "Successfully started bot.",
              timeout: 5000,
              layout: "bottomRight",
              theme: "sunset",
              type: "success"
            }).show();
            $("#start").prop('disabled', true);
            $("#stop").prop('disabled', false);
        } else {
            new Noty({
              text: "Could not start bot. (is it already running?)",
              timeout: 5000,
              layout: "bottomRight",
              theme: "sunset",
              type: "error"
            }).show();
        }
    });
});

$("#stop").click(function() {
    $.get( "/manage/" + botID + "/stop", function( data ) {
        if(data.success) {
            new Noty({
              text: "Successfully stopped bot.",
              timeout: 5000,
              layout: "bottomRight",
              theme: "sunset",
              type: "success"
            }).show();
            $("#stop").prop('disabled', true);
            $("#start").prop('disabled', false);
        } else {
            new Noty({
              text: "Could not stop. (is it running?)",
              timeout: 5000,
              layout: "bottomRight",
              theme: "sunset",
              type: "error"
            }).show();
        }
    });
});