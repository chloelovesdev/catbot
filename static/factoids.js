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

function saveCurrentFactoid(successCallback) {
    $.post("/factoid/" + factoidName + "/save", {
        content: editor.getValue()
    }, function(data) {
        console.log(data)
        if(data.success) {
            successCallback();
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
}

$("#new-modal-save").click(function() {
    window.factoidName = $("#factoid_name").val();
    saveCurrentFactoid(function() {
        window.location.href = "/factoid/" + factoidName;
    });
});

$("#save").click(function() {
    if(factoidName == "new") {
        $("#save-new-factoid").modal();
        return;
    }

    saveCurrentFactoid();
});

$("#test").click(function() {
    if(factoidName == "new") {
        $("#save-new-factoid").modal();
        return;
    }

    saveCurrentFactoid();

    input_command = $("#command-input").val()
    if(input_command == "") {
        input_command = "!" + factoidName;
        $("#command-input").val(input_command);
    }

    $("#test-output").addClass("test-visible");
    $("#test-output-lines").html("<div class=\"line line-text\">Running...</div>");

    $.post("/test", {
        content: input_command
    }, function(data) {
        console.log(data);
        $("#test-output-lines").html("");
        if(data.length == 0) {
            $("#test-output-lines").html("<div class=\"line line-text\">Output from server was empty</div>");
            return;
        }

        for (i = 0; i < data.length; i++) {
            var outputLine = data[i];
            if (outputLine["type"] == "text") {
                var lineEscaped = outputLine["body"].replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/(?:\r\n|\r|\n)/g, '<br>');
                $("<div class=\"line line-text\">" + lineEscaped + "</div>").appendTo("#test-output-lines");
            } else if(outputLine["type"] == "image") {
                $("<div class=\"line line-image\"><img src=\"" + outputLine['url'] + "\" alt=\"" + outputLine['body'] + "\" /></div>").appendTo("#test-output-lines");
            } else if(outputLine["type"] == "html") {
                $("<div class=\"line line-html\">" + outputLine['body'] + "</div>").appendTo("#test-output-lines");
            }
        }
    });
});

$("#test-close").click(function() {
    $("#test-output").removeClass("test-visible");
});