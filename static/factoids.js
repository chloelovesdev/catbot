var editor = ace.edit("editor");
editor.setTheme("ace/theme/monokai");
editor.session.setMode("ace/mode/python");
editor.setValue(window.factoidContent, -1);

$("#save").click(function() {
    $.post("/factoid/" + window.factoidName + "/save", {
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