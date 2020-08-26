$("#defaults").click(function() {
    var checked = $(this).prop("checked");
    
    $("#homeserver").prop("disabled", checked);
    $("#user_id").prop("disabled", checked);
    $("#password").prop("disabled", checked);
});