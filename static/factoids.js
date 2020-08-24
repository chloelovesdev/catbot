var editor = ace.edit("editor");
editor.setTheme("ace/theme/monokai");

var factoidCommandToMode = {
    "python": "ace/mode/python",
    "java": "ace/mode/java",
    "js": "ace/mode/javascript",
    "html": "ace/mode/html"
};

var modeSet = false;
for(factoidCommand in factoidCommandToMode) {
    if(factoidContent.startsWith("<cmd>" + factoidCommand)
    || factoidContent.startsWith("[cmd]" + factoidCommand)
    || window.factoidContent.startsWith("<" + factoidCommand + ">")
    || window.factoidContent.startsWith("[" + factoidCommand + "]")) {
        editor.session.setMode(factoidCommandToMode[factoidCommand]);
        modeSet = true;
    }
}

if (!modeSet) {
    for(factoidCommand in factoidCommandToMode) {
        if(factoidContent.includes(factoidCommand)) {
            editor.session.setMode(factoidCommandToMode[factoidCommand]);
            break;
        }
    }
}

editor.setValue(factoidContent, -1);

$("#save").click(function() {
    if(factoidName == "new") {
        
    }

    $.post("/factoid/" + factoidName + "/save", {
        content: editor.getValue()
    }, function(data) {
        console.log(data)
        if(data.success) {
            new Noty({
              text: "Successfully saved factoid.",
              timeout: 5000,
              layout: "bottomRight",
              theme: "sunset",
              type: "success"
            }).show();
        } else {
            new Noty({
              text: "An error occurred saving the factoid.",
              timeout: 5000,
              layout: "bottomRight",
              theme: "sunset",
              type: "error"
            }).show();
        }
    });
});