console.log("Creating editor")
var editor = ace.edit("editor");
editor.setTheme("ace/theme/monokai");
// editor.setOptions({
//     maxLines: 500,
//     minLines: 50
// });
editor.session.setMode("ace/mode/python");