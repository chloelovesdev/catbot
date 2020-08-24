var editor = ace.edit("editor");
editor.setTheme("ace/theme/monokai");

var factoidCommandToMode = {
    "python": "ace/mode/python",
    "java": "ace/mode/java",
    "html": "ace/mode/html"
};

for(factoidCommand in factoidCommandToMode) {
    if(factoidContent.startsWith("<cmd>" + factoidCommand) || window.factoidContent.startsWith("<" + factoidCommand + ">")) {
        editor.session.setMode(factoidCommandToMode[factoidCommand]);
    }
}

editor.setValue(factoidContent, -1);

$("#save").click(function() {
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