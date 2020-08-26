$("#all_enabled").click(function() {
    if($(this).prop('checked')) {
        $("#modules").find("input[type=\"checkbox\"]").prop("disabled", true);
        $("#modules").find("input[type=\"checkbox\"]").prop("checked", true);
        $("#all_enabled").prop("disabled", false);
    } else {
        $("#modules").find("input[type=\"checkbox\"]").prop("disabled", false);
        $("#modules").find("input[type=\"checkbox\"]").prop("checked", true);
        $("#all_enabled").prop("checked", false);
    }
});