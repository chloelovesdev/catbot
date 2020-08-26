$(".user-checkbox").click(function() {
    var devicesForUser = $(this).closest(".user").find(".device");
    if($(this).prop('checked')) {
        devicesForUser.find(".device-checkbox").prop("disabled", true);
        devicesForUser.find(".device-checkbox").prop("checked", true);
        $(this).prop("disabled", false);
    } else {
        devicesForUser.find(".device-checkbox").prop("disabled", false);
        devicesForUser.find(".device-checkbox").prop("checked", true);
        $(this).prop("checked", false);
    }
});

$("#trust_all").click(function() {
    if($(this).prop('checked')) {
        $("#trust").find("input[type=\"checkbox\"]").prop("disabled", true);
        $("#trust").find("input[type=\"checkbox\"]").prop("checked", true);
        $("#trust_all").prop("disabled", false);
    } else {
        $("#trust").find("input[type=\"checkbox\"]").prop("disabled", false);
        $("#trust").find("input[type=\"checkbox\"]").prop("checked", true);
        $("#trust_all").prop("checked", false);
        $(".device-checkbox").prop("disabled", true);
    }
});